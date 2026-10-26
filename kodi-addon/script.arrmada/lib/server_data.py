# -*- coding: utf-8 -*-
"""Adresse du serveur ArrMada : logique pure, sans Kodi (testée en CI).

Jusqu'à la 1.25.0 incluse, une adresse vide (ou 127.0.0.1 / localhost) était
remplacée par l'IP du réseau du mainteneur, puis enregistrée dans les
réglages : sur une nouvelle installation (Synology chez quelqu'un d'autre),
la TV interrogeait une machine qui n'existe pas chez lui et gardait cette
adresse. Désormais, pas d'adresse = « Serveur ArrMada non configuré » : les
écrans proposent de chercher le serveur sur le réseau ou de saisir son
adresse, puis l'appairage.

D'où vient l'adresse, dans l'ordre :
  1. le réglage `server_url` de l'add-on (TV déjà configurée : inchangé) ;
  2. sinon, le serveur avec lequel la TV est appairée (`device.json`) : une
     TV qui se fiait à l'ancienne valeur par défaut des réglages la retrouve.
"""

from __future__ import annotations

import ipaddress
import urllib.parse
from typing import Any, List

API_PORT = 8420  # port de l'API (celui que la TV interroge)
WEB_PORT = 3420  # port de la web app : saisi par erreur, on passe sur l'API
HEALTH_PATH = "/api/health"  # route publique : {"status": "ok", "service": "arrmada", …}

# Le nom de la TV elle-même : une adresse vers elle ne peut pas être le serveur.
LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")

NOT_CONFIGURED_TITLE = "Serveur ArrMada non configuré"
NOT_CONFIGURED_MESSAGE = (
    "Serveur ArrMada non configuré : recherche-le sur le réseau ou saisis son adresse "
    "(Réglages de l'accueil ArrMada)."
)
REASON_NOT_CONFIGURED = "not_configured"


def normalize_url(raw: str) -> str:
    """Adresse saisie → adresse de l'API (« » si rien d'utilisable).

    « nas:3420/ » → « http://nas:8420 » : schéma ajouté, « / » final retiré,
    port de la web app remplacé par celui de l'API. Une adresse vers la TV
    elle-même (localhost, 127.0.0.1) compte comme « non configurée ».
    """
    url = (raw or "").strip().rstrip("/")
    if not url:
        return ""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"http://{url}"
    try:
        parts = urllib.parse.urlsplit(url)
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:  # port non numérique (« nas:abc ») : laissé tel quel
        return url
    if not host or host in LOOPBACK_HOSTS:
        return ""
    if port == WEB_PORT:
        # Même conversion qu'avant : seul le port change, le reste est gardé
        netloc = parts.netloc.rsplit(":", 1)[0] + f":{API_PORT}"
        url = urllib.parse.urlunsplit(parts._replace(netloc=netloc))
    return url


def resolve_server_url(setting: str, paired_server: str = "") -> str:
    """Adresse à utiliser : le réglage, sinon le serveur de l'appairage, sinon « »."""
    return normalize_url(setting) or normalize_url(paired_server)


def not_configured_error() -> dict:
    """Réponse d'erreur de lib/api.py quand aucune adresse n'est réglée.

    Même forme que les autres erreurs ({"status": "error", "message": …}) :
    les écrans existants l'affichent sans changement. `reason` permet de
    dire « non configuré » plutôt que « injoignable » (home_data.describe_error).
    """
    return {
        "status": "error",
        "reason": REASON_NOT_CONFIGURED,
        "message": NOT_CONFIGURED_MESSAGE,
    }


def is_not_configured(response: Any) -> bool:
    return isinstance(response, dict) and response.get("reason") == REASON_NOT_CONFIGURED


# ─────────────────────────────────────────────────────────────────────────────
# Recherche sur le réseau local
# ─────────────────────────────────────────────────────────────────────────────


def scan_hosts(local_ip: str) -> List[str]:
    """Adresses à essayer : le /24 de la TV (« 192.168.1.x »), sans la TV elle-même.

    Analogie : un `for i in $(seq 1 254); do curl -m1 http://192.168.1.$i:8420/api/health`.
    IP inconnue, IPv6 ou adresse publique : rien à balayer (saisie à la main).
    """
    try:
        address = ipaddress.IPv4Address((local_ip or "").strip())
    except ValueError:
        return []
    if not address.is_private or address.is_loopback or address.is_link_local:
        return []
    network = ipaddress.IPv4Network(f"{address}/24", strict=False)
    return [str(host) for host in network.hosts() if host != address]


def candidate_url(host: str, port: int = API_PORT) -> str:
    return f"http://{host}:{port}"


def is_arrmada_health(payload: Any) -> bool:
    """Réponse de /api/health : est-ce bien un serveur ArrMada (pas un autre service) ?"""
    return isinstance(payload, dict) and str(payload.get("service") or "").lower() == "arrmada"


def found_label(url: str, payload: Any) -> str:
    """Ligne de la liste des serveurs trouvés : « http://192.168.1.49:8420 · ArrMada 1.40.2 »."""
    version = str(payload.get("version") or "") if isinstance(payload, dict) else ""
    return f"{url} · ArrMada {version}" if version else f"{url} · ArrMada"


def sort_hosts(urls: List[str]) -> List[str]:
    """Serveurs trouvés dans l'ordre des adresses (192.168.1.9 avant 192.168.1.10)."""

    def key(url: str):
        host = urllib.parse.urlsplit(url).hostname or ""
        try:
            return (0, int(ipaddress.IPv4Address(host)), url)
        except ValueError:
            return (1, 0, url)

    return sorted(urls, key=key)
