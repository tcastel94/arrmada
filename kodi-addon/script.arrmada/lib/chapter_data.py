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

Sans chapitres nommés (« Chapitre 01 »…), rien ne s'affiche : aucune
devinette sur la position de l'intro.

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
