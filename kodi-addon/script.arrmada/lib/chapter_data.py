# -*- coding: utf-8 -*-
"""« Passer l'intro » d'après les chapitres du fichier : logique pure (testée en CI).

Beaucoup de fichiers (WEB-DL, animés, certains Blu-ray) nomment leurs
chapitres : « Intro », « Opening », « Générique », « Previously on »,
« Credits », « Ending »… Le service regarde le chapitre en cours une fois
par seconde :

  - chapitre d'intro ou de récapitulatif → bouton « Passer l'intro » /
    « Passer le récap » en bas à droite, 10 s ; OK saute au chapitre suivant ;
  - chapitre de générique de fin d'un épisode → l'encart « Épisode suivant »
    s'ouvre tout de suite, sans attendre les 20 dernières secondes.

Sans chapitres nommés (« Chapitre 01 »…) : marqueurs calculés par Jellyfin
(1.25.0, plugin Intro Skipper ou Chapter Segments Provider), demandés au
serveur ArrMada au début de l'épisode : `segment_offer_at` / `segment_credits_at`.
Sans l'un ni l'autre, rien ne s'affiche : aucune devinette sur la position.

Sous Kodi 20, le « chapitre en cours » du lecteur ne bouge pas pendant une
lecture normale (vérifié sur le banc). Pour les MKV, on lit donc la liste
des chapitres dans le fichier (lib/mkv_chapters.py) et on la compare à la
position : `skip_offer_at` / `credits_at`. Les autres formats gardent
l'information de Kodi (`skip_offer` / `credits_started`), à jour après un saut.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

ACTION = "skip"  # plugin://script.arrmada/?action=skip&kind=intro
POPUP_PROP = "arrmada.skip_open"  # « 1 » tant que le bouton est affiché
DISPLAY_SECONDS = 10

# Nom de chapitre → sorte (motifs en minuscules, sans accents)
_PATTERNS = (
    ("recap", r"\b(recap|previously|precedemment|resume|résumé|dans les episodes precedents)\b"),
    ("credits", r"\b(end ?credits|credits|ending|outro|generique de fin|ed)\b"),
    ("intro", r"\b(intro|introduction|opening|generique|title sequence|op|theme)\b"),
)

LABELS = {"intro": "Passer l'intro", "recap": "Passer le récap"}

_ACCENTS = str.maketrans("éèêëàâäîïôöùûüç", "eeeeaaaiioouuuc")


def _plain(name: Any) -> str:
    return str(name or "").strip().lower().translate(_ACCENTS)


def chapter_kind(name: Any) -> str:
    """« Opening » → « intro », « End Credits » → « credits », « Chapitre 3 » → ""."""
    text = _plain(name)
    if not text or re.fullmatch(r"(chapter|chapitre|kapitel|capitulo|ch)\s*\d+", text):
        return ""
    for kind, pattern in _PATTERNS:
        if re.search(pattern, text):
            return kind
    return ""


def skip_offer(
    name: Any, index: int, count: int, offered: set, file: str
) -> Optional[Dict[str, str]]:
    """Bouton à proposer pour ce chapitre, ou None.

    `offered` : chapitres déjà proposés pour ce fichier (une fois chacun) ;
    il faut un chapitre suivant où sauter.
    """
    kind = chapter_kind(name)
    if kind not in LABELS or index <= 0 or index >= count or (file, index) in offered:
        return None
    return {"action": ACTION, "kind": kind, "label": LABELS[kind], "chapter": str(index)}


def chapter_at(chapters: List[Tuple[float, str]], seconds: float):
    """(n° à partir de 1, nom, début, début du suivant ou None) ; None avant le 1er."""
    current = None
    for index, (start, name) in enumerate(chapters or [], 1):
        if start <= seconds:
            following = chapters[index][0] if index < len(chapters) else None
            current = (index, name, start, following)
        else:
            break
    return current


def skip_offer_at(
    chapters: List[Tuple[float, str]], seconds: float, offered: set, file: str
) -> Optional[Dict[str, str]]:
    """Comme `skip_offer`, d'après la liste des chapitres du fichier et la position.

    Le bouton saute à l'heure exacte du chapitre suivant (`to`) et disparaît
    quand on l'atteint (`until`). Rien dans les 2 dernières secondes de
    l'intro : le saut n'aurait plus d'intérêt.
    """
    current = chapter_at(chapters, seconds)
    if current is None:
        return None
    index, name, _, following = current
    kind = chapter_kind(name)
    if kind not in LABELS or following is None or (file, index) in offered:
        return None
    if following - seconds < 2:
        return None
    return {
        "action": ACTION,
        "kind": kind,
        "label": LABELS[kind],
        "chapter": str(index),
        "to": f"{following:.1f}",
        "until": f"{following:.1f}",
    }


def credits_at(chapters: List[Tuple[float, str]], seconds: float, is_episode: bool) -> bool:
    current = chapter_at(chapters, seconds)
    return bool(is_episode and current and chapter_kind(current[1]) == "credits")


def credits_started(name: Any, is_episode: bool) -> bool:
    """Générique de fin d'un épisode : l'encart « Épisode suivant » peut s'ouvrir."""
    return is_episode and chapter_kind(name) == "credits"


# ── Marqueurs de Jellyfin (1.25.0) : quand le fichier n'a pas de chapitres nommés ──

# Numérotés à part des chapitres (1001, 1002…) dans l'ensemble « déjà proposés »
SEGMENT_BASE = 1000


def parse_segments(response: Any) -> List[Dict[str, Any]]:
    """Réponse de GET /api/kodi/segments → [{kind, start, end}] valides, triés."""
    if not isinstance(response, dict) or response.get("status") != "ok":
        return []
    out = []
    for seg in response.get("segments") or []:
        if not isinstance(seg, dict) or seg.get("kind") not in ("intro", "recap", "credits"):
            continue
        try:
            start, end = float(seg.get("start")), float(seg.get("end"))
        except (TypeError, ValueError):
            continue
        if end > start >= 0:
            out.append({"kind": seg["kind"], "start": start, "end": end})
    return sorted(out, key=lambda seg: seg["start"])


def segment_offer_at(
    segments: List[Dict[str, Any]], seconds: float, offered: set, file: str
) -> Optional[Dict[str, str]]:
    """Bouton à proposer pendant une intro / un récap repéré par Jellyfin, ou None.

    Même forme que `skip_offer_at` : saut à la fin du marqueur (`to`), bouton
    retiré quand on l'atteint (`until`), une seule fois par marqueur.
    """
    for index, seg in enumerate(segments or [], 1):
        if seg["kind"] not in LABELS or not seg["start"] <= seconds < seg["end"]:
            continue
        key = SEGMENT_BASE + index
        if (file, key) in offered or seg["end"] - seconds < 2:
            return None
        return {
            "action": ACTION,
            "kind": seg["kind"],
            "label": LABELS[seg["kind"]],
            "chapter": str(key),
            "to": f"{seg['end']:.1f}",
            "until": f"{seg['end']:.1f}",
        }
    return None


def segment_credits_at(segments: List[Dict[str, Any]], seconds: float) -> bool:
    """Générique de fin repéré par Jellyfin : « Épisode suivant » peut s'ouvrir."""
    return any(
        seg["kind"] == "credits" and seg["start"] <= seconds < seg["end"] for seg in segments or []
    )
