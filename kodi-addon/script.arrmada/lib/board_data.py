# -*- coding: utf-8 -*-
"""Écran Téléchargements (ADR-005, lot 3) : la logique, sans Kodi (testée en CI).

Le serveur envoie le tableau (GET /api/kodi/downloads/board) ; ce module en
tire ce que l'écran affiche :
  - les cartes « Pour ce soir » : heure « Prêt vers 20:58 », étapes du
    parcours (Trouvé → Téléchargement → Import → Prêt), TV d'origine ;
  - les actions de chaque carte et de chaque ligne de la file (menu de OK) ;
  - le résumé de l'en-tête et le contenu du dialogue « Débloquer ».
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from screens_data import bar_texture, human_bytes

# Import + sous-titres après la fin du téléchargement : marge ajoutée à l'heure
# « Prêt vers » (un import Sonarr/Radarr prend en général 1 à 2 minutes).
READY_MARGIN = timedelta(minutes=2)

STEPS = ("Trouvé", "Téléchargement", "Import", "Prêt")

# Étape en cours selon la phase : (états des 4 étapes)
_STEP_STATES = {
    "searching": ("now", "", "", ""),
    "downloading": ("done", "now", "", ""),
    "importing": ("done", "done", "now", ""),
    "ready": ("done", "done", "done", "done"),
    "notfound": ("err", "", "", ""),
}

_HEADLINES = {
    "searching": "Recherche d'une version…",
    "importing": "Import sur le NAS…",
    "ready": "Prêt à regarder",
    "notfound": "Introuvable pour l'instant",
}

ACTION_LABELS = {
    "detail": "Fiche du titre",
    "unstick": "Débloquer",
    "search": "Relancer la recherche",
    "cancel": "Annuler ma demande",
    "top": "Passer en tête",
    "pause": "Mettre en pause",
    "resume": "Reprendre",
}


# Libellés courts de l'indice « OK : … » (une ligne étroite sous la carte / la ligne)
HINT_LABELS = {
    "detail": "Fiche",
    "unstick": "Débloquer",
    "search": "Rechercher",
    "cancel": "Annuler",
    "top": "En tête",
    "pause": "Pause",
    "resume": "Reprendre",
}


def hint(actions: List[Tuple[str, str]]) -> str:
    """« OK : En tête · Pause · Fiche » (vide sans action)."""
    return "OK : " + " · ".join(HINT_LABELS[op] for op, _ in actions) if actions else ""


def parse_iso(value: Any) -> Optional[datetime]:
    """« 2026-10-17T20:41:05+00:00 » → datetime en heure locale de la TV ; illisible → None."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is not None:
        moment = moment.astimezone().replace(tzinfo=None)  # heure locale, comme `now`
    return moment


def ago(value: Any, now: datetime) -> str:
    """« à l'instant », « il y a 4 min », « il y a 2 h », sinon « à 19:02 »."""
    moment = parse_iso(value)
    if moment is None:
        return ""
    minutes = int((now - moment).total_seconds() // 60)
    if minutes < 1:
        return "à l'instant"
    if minutes < 60:
        return f"il y a {minutes} min"
    if minutes < 6 * 60:
        return f"il y a {minutes // 60} h"
    return f"à {moment:%H:%M}"


def ready_at(seconds: Optional[int], now: datetime) -> str:
    """Heure à laquelle ce sera prêt (fin du téléchargement + import), « 20:58 »."""
    if seconds is None:
        return ""
    moment = now + timedelta(seconds=int(seconds)) + READY_MARGIN
    if moment.second or moment.microsecond:  # arrondi à la minute supérieure
        moment = moment.replace(second=0, microsecond=0) + timedelta(minutes=1)
    return f"{moment:%H:%M}"


def _short(text: str, limit: int = 70) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def card_actions(card: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Menu de OK sur une carte « Pour ce soir »."""
    ops = []
    if card.get("phase") == "blocked" and card.get("blocked_download"):
        ops.append("unstick")
    if card.get("phase") in ("searching", "notfound"):
        ops.append("search")
    if card.get("arr_id"):
        ops.append("detail")
    if card.get("can_cancel"):
        ops.append("cancel")
    return [(op, ACTION_LABELS[op]) for op in ops]


def card_model(card: Dict[str, Any], now: datetime) -> Dict[str, str]:
    """Propriétés d'une carte « Pour ce soir » (voir script-arrmada-downloads.xml)."""
    phase = str(card.get("phase") or "searching")
    pct = float(card.get("progress") or 0)
    states = list(_STEP_STATES.get(phase, ("", "", "", "")))
    if phase == "blocked":  # bloqué au téléchargement, ou à l'import
        states = ["done", "done", "err", ""] if pct >= 100 else ["done", "err", "", ""]

    if phase == "downloading":
        when = ready_at(card.get("time_left_seconds"), now)
        headline = f"Prêt vers {when}" if when else f"Téléchargement {round(pct)} %"
    elif phase == "blocked":
        headline = "Bloqué"
    else:
        headline = _HEADLINES.get(phase, "")

    who = [str(card.get("device_name") or "TV"), ago(card.get("requested_at"), now)]
    if card.get("quality"):
        who.append(str(card["quality"]))
    size = float(card.get("size_bytes") or 0)
    if size:
        who.append(human_bytes(size))
    detail = ""
    if phase == "blocked":
        detail = _short(card.get("error") or "Le téléchargement n'avance plus")
    elif phase == "downloading":
        detail = f"{round(pct)} %"
        if card.get("protocol") == "torrent":
            detail += " · torrent : pas de priorité possible"
    elif phase == "notfound":
        detail = "Aucune release pour l'instant"
    actions = card_actions(card)
    model = {
        "key": f"req:{card.get('id')}",
        "label": str(card.get("title") or ""),
        "who": " · ".join(w for w in who if w),
        "headline": headline,
        "detail": detail,
        "phase": phase,
        "bar": bar_texture(pct),
        "poster": str(card.get("poster_url") or ""),
        "fanart": str(card.get("fanart_url") or ""),
        "hint": hint(actions),
        "mine": "1" if card.get("mine") else "",
    }
    for index, (label, state) in enumerate(zip(STEPS, states), start=1):
        model[f"s{index}"] = label
        model[f"s{index}_state"] = state
    return model


def row_actions(row: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Menu de OK sur une ligne de la file (actions SABnzbd pour l'Usenet seulement)."""
    ops = []
    family = row.get("family")
    usenet = bool(row.get("download_id")) and row.get("protocol") == "usenet"
    if family == "error" and row.get("download_id"):
        ops.append("unstick")
    if usenet and family in ("active", "queued", "paused"):
        ops.append("top")
        ops.append("resume" if family == "paused" else "pause")
    if row.get("arr_id"):
        ops.append("detail")
    return [(op, ACTION_LABELS[op]) for op in ops]


def decorate_rows(rows: List[Dict[str, Any]], items: List[Dict[str, Any]]) -> None:
    """Complète les lignes de screens_data.build_downloads : id SABnzbd, actions, indice."""
    for row, item in zip(rows, items):
        row["download_id"] = str(item.get("download_id") or "")
        row["protocol"] = str(item.get("protocol") or "")
        row["poster"] = str(item.get("poster_url") or "")
        actions = row_actions(row)
        row["actions"] = actions
        row["hint"] = hint(actions)
        # « 12 min · 5,0 Mo/s », sans séparateur orphelin si l'un des deux manque
        row["eta_speed"] = " · ".join(v for v in (row.get("eta"), row.get("speed")) if v)


def summary(cards: List[Dict[str, Any]], rows: List[Dict[str, Any]], sab: Any) -> str:
    """En-tête : « 2 pour ce soir · 7 en file · 48,2 Mo/s · SABnzbd en pause »."""
    running = sum(1 for c in cards if c.get("status") == "open")
    parts = []
    if running:
        parts.append(f"{running} pour ce soir")
    parts.append(f"{len(rows)} en file" if rows else "file vide")
    if isinstance(sab, dict):
        speed = float(sab.get("kbpersec") or 0) * 1024
        if speed > 0:
            parts.append(f"{human_bytes(speed)}/s")
        if sab.get("paused"):
            parts.append("SABnzbd en pause (sauf ce soir)" if running else "SABnzbd en pause")
    return " · ".join(parts)


def unstick_model(diag: Any) -> Dict[str, Any]:
    """Dialogue « Débloquer » : 3 lignes au plus, bouton d'action ou non."""
    if not isinstance(diag, dict) or diag.get("status") != "ok":
        message = diag.get("message") if isinstance(diag, dict) else ""
        return {
            "steps": [("err", "Diagnostic impossible", message or "Serveur injoignable")],
            "action": "",
            "can_fix": False,
        }
    steps = [
        (str(s.get("state") or ""), str(s.get("text") or ""), _short(s.get("detail") or "", 90))
        for s in diag.get("steps") or []
    ][:3]
    return {
        "steps": steps,
        "action": str(diag.get("action") or ""),
        "can_fix": bool(diag.get("can_fix")),
    }
