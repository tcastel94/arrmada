# -*- coding: utf-8 -*-
"""« Serveur ArrMada non configuré » : trouver le serveur ou saisir son adresse (1.25.2).

Ouvert avant l'appairage quand la TV ne connaît aucune adresse (nouvelle
installation), et depuis Réglages de l'accueil › « Trouver le serveur
ArrMada » / « Changer de serveur ». Deux façons :
  - recherche sur le réseau : chaque adresse du /24 de la TV est essayée sur
    le port 8420 (`/api/health`, route publique), 32 à la fois, 0,8 s maxi
    chacune : une dizaine de secondes au pire ;
  - saisie de l'adresse au clavier (serveur sur un autre réseau, VPN…).

L'adresse choisie va dans le réglage `server_url` de l'add-on. Le jeton de
la TV est lié à l'adresse (lib/device.py) : changer de serveur demande un
nouvel appairage, proposé juste après. Logique pure : lib/server_data.py.
"""

from __future__ import annotations

import json
import socket
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

import xbmc
import xbmcgui

import server_data
import ui_common as ui
from api import ArrMadaAPI

PROBE_TIMEOUT = 0.8  # s par adresse : un serveur du réseau local répond bien plus vite
PROBE_WORKERS = 32  # adresses essayées en parallèle

CHOICE_SCAN = "Rechercher sur le réseau"
CHOICE_INPUT = "Saisir l'adresse du serveur"


def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    ui.log("Serveur", message, level)


def probe(url: str, timeout: float = PROBE_TIMEOUT) -> Optional[dict]:
    """Réponse de /api/health si `url` est un serveur ArrMada, sinon None."""
    request = urllib.request.Request(
        f"{url}{server_data.HEALTH_PATH}", headers={"User-Agent": "ArrMada-Kodi-Addon"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read(4096).decode("utf-8"))
    except Exception:  # rien sur ce port, autre service, réponse illisible…
        return None
    return payload if server_data.is_arrmada_health(payload) else None


def _local_ip() -> str:
    """Adresse de la TV sur le réseau local (« » si inconnue)."""
    address = (xbmc.getIPAddress() or "").strip()
    if address and not address.startswith("127."):
        return address
    # Repli : l'adresse source qu'utiliserait le système pour sortir (aucun
    # paquet n'est envoyé par un connect() UDP). Analogie : `ip route get`.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
    except OSError:
        return ""


def scan(progress: xbmcgui.DialogProgress) -> List[Tuple[str, dict]]:
    """Serveurs ArrMada du réseau local : [(adresse, réponse de /api/health)]."""
    hosts = server_data.scan_hosts(_local_ip())
    if not hosts:
        return []
    found: dict = {}
    with ThreadPoolExecutor(max_workers=PROBE_WORKERS) as pool:
        futures = {pool.submit(probe, server_data.candidate_url(host)): host for host in hosts}
        for done, future in enumerate(as_completed(futures), start=1):
            payload = future.result()
            if payload:
                found[server_data.candidate_url(futures[future])] = payload
            progress.update(
                int(done * 100 / len(hosts)),
                f"{done} / {len(hosts)} adresses essayées, {len(found)} serveur(s) trouvé(s)",
            )
            if progress.iscanceled():
                # Les essais pas encore lancés sont annulés ; la sortie du
                # `with` attend les autres (0,8 s maxi) : aucun fil orphelin.
                for pending in futures:
                    pending.cancel()
                break
    return [(url, found[url]) for url in server_data.sort_hosts(list(found))]


def _search() -> str:
    """Recherche sur le réseau, puis choix du serveur : son adresse (« » si aucune)."""
    progress = xbmcgui.DialogProgress()
    progress.create("Recherche du serveur ArrMada", "Adresses du réseau local, port 8420…")
    try:
        servers = scan(progress)
    finally:
        progress.close()
    _log(f"recherche sur le réseau : {len(servers)} serveur(s) trouvé(s)")
    if not servers:
        xbmcgui.Dialog().ok(
            "Aucun serveur ArrMada trouvé",
            "Vérifie que le serveur tourne et que la TV est sur le même réseau, "
            "ou saisis son adresse (exemple : http://192.168.1.10:8420).",
        )
        return ""
    labels = [server_data.found_label(url, payload) for url, payload in servers]
    index = xbmcgui.Dialog().select("Serveurs ArrMada trouvés", labels)
    return servers[index][0] if index >= 0 else ""


def _input(current: str) -> str:
    """Saisie de l'adresse au clavier, vérifiée avant d'être gardée (« » si annulé)."""
    typed = xbmcgui.Dialog().input(
        "Adresse du serveur ArrMada (exemple : http://192.168.1.10:8420)",
        defaultt=current or "http://",
    )
    url = server_data.normalize_url(typed)
    if not url:
        if (typed or "").strip() not in ("", "http://", "https://"):
            xbmcgui.Dialog().ok(
                server_data.NOT_CONFIGURED_TITLE,
                "Cette adresse désigne la TV elle-même : saisis celle du serveur "
                "(NAS, PC), par exemple http://192.168.1.10:8420.",
            )
        return ""
    if probe(url, timeout=5) is None:
        keep = xbmcgui.Dialog().yesno(
            "Serveur ArrMada injoignable",
            f"Aucun serveur ArrMada ne répond à {url}. L'enregistrer quand même ?",
            nolabel="Corriger",
            yeslabel="Enregistrer",
        )
        if not keep:
            return _input(typed)
    return url


def choose_server() -> bool:
    """Menu « Trouver le serveur ArrMada » ; vrai si une adresse a été enregistrée."""
    current = ArrMadaAPI.get_config()["url"]
    title = f"Serveur ArrMada : {current}" if current else server_data.NOT_CONFIGURED_TITLE
    while True:
        index = xbmcgui.Dialog().select(title, [CHOICE_SCAN, CHOICE_INPUT])
        if index < 0:
            return False
        url = _search() if index == 0 else _input(current)
        if url:
            break
    ArrMadaAPI.set_server_url(url)
    _log(f"adresse enregistrée : {url}")
    ui.notify("ArrMada", f"Serveur enregistré : {url}", 5000)
    return True


def ensure_configured() -> bool:
    """Vrai si une adresse est réglée ; sinon propose de trouver le serveur."""
    if ArrMadaAPI.get_config()["url"]:
        return True
    _log("aucune adresse de serveur réglée : recherche proposée")
    return choose_server()
