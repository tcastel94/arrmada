# -*- coding: utf-8 -*-
"""Alertes des caméras Eufy sur la TV : logique pure, sans Kodi (testée en CI).

Le serveur publie un événement « camera » quand une caméra détecte une
personne (eufy-security-ws → ArrMada) :
  {camera, serial, detection, label, snapshot_id, at}
Le service de l'add-on le relève (toutes les 5 s) et :
  - pendant un film ou un épisode : pop-up compacte en haut à gauche, avec
    la photo, 5 s, sans mettre la lecture en pause (lib/camera_window.py) ;
  - sinon : une bulle de notification, avec la photo en vignette.
Contrairement aux autres notifications, une alerte caméra n'est jamais
retenue pour le résumé « Pendant ta séance » : c'est maintenant qu'elle compte.
"""

from __future__ import annotations

from datetime import datetime, timezone, tzinfo
from typing import Any, Dict, Mapping, Optional

EVENT = "camera"
DISPLAY_SECONDS = 5  # durée de la pop-up (toute touche la ferme avant) ; 15 s avant la 1.14.1
NOTIFY_MS = 10000  # durée de la bulle hors lecture
SNAPSHOT_KEEP = 5  # photos gardées dans le cache de l'add-on
POPUP_PROP = "arrmada.camera_popup"  # « 1 » tant qu'une pop-up est ouverte


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def snapshot_id(data: Mapping[str, Any]) -> int:
    """Numéro de la photo de l'événement (0 : pas de photo)."""
    return max(0, _int(data.get("snapshot_id")))


def clock(value: Any, tz: Optional[tzinfo] = None) -> str:
    """« 2026-10-11T19:42:05+00:00 » → « 21:42 » à l'heure locale ; "" si illisible."""
    try:
        moment = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return ""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(tz) if tz else moment.astimezone()
    return f"{local.hour:02d}:{local.minute:02d}"


def popup(
    data: Mapping[str, Any], tz: Optional[tzinfo] = None, local_time: str = ""
) -> Dict[str, str]:
    """Textes de la pop-up : titre (« Personne détectée »), caméra, heure.

    `local_time` : l'heure donnée par Kodi lui-même (« 21:42 »). Sur Android,
    le fuseau horaire vu par Python n'est pas toujours celui de la TV ; Kodi,
    lui, affiche la bonne heure. L'alerte arrive quelques secondes après la
    détection : son heure d'arrivée suffit.
    """
    when = local_time or clock(data.get("at"), tz)
    camera = str(data.get("camera") or "Caméra")
    return {
        "title": str(data.get("label") or "Détection"),
        "camera": camera,
        "time": when,
        "subtitle": f"{camera} · {when}" if when else camera,
    }


def bubble(
    data: Mapping[str, Any], icon: str = "", tz: Optional[tzinfo] = None, local_time: str = ""
) -> Dict:
    """Bulle hors lecture : « Personne détectée » / « Entrée · 21:42 »."""
    texts = popup(data, tz, local_time)
    return {"heading": texts["title"], "message": texts["subtitle"], "icon": icon}


def wants_popup(watching: bool, enabled: bool, popup_open: bool) -> str:
    """« popup », « bubble » ou "" (alertes coupées dans les réglages)."""
    if not enabled:
        return ""
    if watching and not popup_open:
        return "popup"
    return "bubble"


def file_name(snapshot: int, stamp: int) -> str:
    """Nom du fichier de la photo dans le cache : un par photo ET par moment.

    Les numéros de photo repartent de 1 quand le serveur redémarre : sans
    l'horodatage, Kodi pourrait réafficher une ancienne photo gardée en cache
    sous le même nom.
    """
    return f"arrmada-camera-{snapshot}-{stamp}.jpg"
