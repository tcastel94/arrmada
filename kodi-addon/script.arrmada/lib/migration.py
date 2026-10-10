# -*- coding: utf-8 -*-
"""Passage de l'ancien mot de passe admin à l'appairage (ADR-003, phase 3).

Jusqu'à la 1.7, une TV pouvait se connecter avec le mot de passe admin
d'ArrMada (réglage « Clé API / Mot de passe »). Depuis la 1.8, la TV
n'envoie plus que son propre jeton (lib/api.py) : une TV volée ou
compromise ne donne plus les droits admin. Le serveur, lui, accepte
toujours ce mot de passe pour les scripts et automatisations.

Une TV qui a encore le mot de passe dans ses réglages s'appaire TOUTE SEULE
au démarrage du service, comme si on validait son code dans la web app :
  1. elle demande un code (`/pair/start`) ;
  2. elle le valide elle-même avec le mot de passe (`/pair/confirm`), en
     reprenant ses réglages « Nom de l'appareil » et « Profil de la pièce » ;
  3. elle récupère son jeton (`/pair/poll`) ;
  4. elle EFFACE le mot de passe de ses réglages.
L'ampli de la pièce se choisit ensuite dans la web app (Paramètres → Kodi →
Appareils) ; d'ici là, le serveur prend le premier ampli actif, comme avant.

Analogie : un serveur qui se connectait en root par mot de passe et qui,
au premier démarrage, dépose sa clé SSH puis efface le mot de passe.
"""

from __future__ import annotations

import xbmc
import xbmcaddon

import device
import pairing_data
import ui_common as ui
from api import ArrMadaAPI

ROOM_LABELS = {"salon": "Salon", "cinema": "Salle de cinéma"}


def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    xbmc.log(f"[ArrMada] Migration : {message}", level)


def needed() -> bool:
    """Vrai si l'ancien mot de passe est encore dans les réglages."""
    return bool(ArrMadaAPI.get_config()["api_key"])


def _forget_password() -> None:
    """Efface le mot de passe des réglages (settings.xml de l'add-on).

    Copie neuve de l'add-on : chaque module garde la sienne, et enregistrer
    depuis une copie ancienne réécrirait aussi ses autres réglages périmés.
    """
    xbmcaddon.Addon("script.arrmada").setSetting("api_key", "")


def run() -> str:
    """Une tentative de migration : « done », « refused » ou « retry ».

    done    : TV appairée (ou déjà appairée), mot de passe effacé ;
    refused : mot de passe refusé par le serveur, effacé aussi (il ne sert
              plus à rien) : la TV propose « Appairer cette TV » ;
    retry   : serveur injoignable, on réessaiera plus tard (mot de passe gardé).
    """
    config = ArrMadaAPI.get_config()
    password = config["api_key"]
    if not password:
        return "done"
    if device.token_for(config["url"]):
        _forget_password()
        _log("TV déjà appairée : ancien mot de passe effacé")
        return "done"

    started = ArrMadaAPI.pair_start(ui.platform_name())
    if started.get("status") == "error" or not started.get("device_code"):
        _log(f"demande de code impossible : {started.get('message')}", xbmc.LOGWARNING)
        return "retry"

    name = (config.get("device_name") or "Kodi").strip() or "Kodi"
    room = pairing_data.migration_room(ui.ADDON.getSetting("room_profile"))
    confirmed = ArrMadaAPI.pair_confirm_with_password(started["user_code"], name, room, password)
    outcome = pairing_data.migration_confirm_outcome(confirmed)
    if outcome == "refused":
        _forget_password()
        _log(f"mot de passe refusé ({confirmed.get('message')}) : effacé", xbmc.LOGWARNING)
        ui.notify("Appairage nécessaire", "Menu ArrMada, puis « Appairer cette TV »", 10000)
        return "refused"
    if outcome == "retry":
        _log(f"validation impossible : {confirmed.get('message')}", xbmc.LOGWARNING)
        return "retry"

    polled = ArrMadaAPI.pair_poll(started["device_code"])
    state, message = pairing_data.poll_outcome(polled)
    if state != "ok":
        _log(f"jeton non reçu ({state}) : {message}", xbmc.LOGWARNING)
        return "retry"
    info = polled.get("device") or {}
    device.save(config["url"], polled["token"], info)
    _forget_password()
    summary = pairing_data.device_summary(info) or f"{name} · {ROOM_LABELS.get(room, room)}"
    _log(f"TV appairée automatiquement ({summary}), ancien mot de passe effacé")
    ui.notify("Cette TV est appairée", f"{summary} · mot de passe effacé", 10000)
    return "done"
