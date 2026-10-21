"""Appairage des Kodi (ADR-003 § 4) : codes, jetons, périmètre « TV ».

Le principe est celui de « connecter la TV » de Netflix (RFC 8628, *Device
Authorization Grant*) :

  1. Kodi demande un appairage (`start`) : il reçoit un **code court** à
     afficher (« K7P4QX ») et un **code secret** qu'il garde pour lui ;
  2. dans la web app, tu saisis le code court (ou tu scannes le QR code),
     puis tu choisis le nom, la pièce et l'ampli de l'appareil (`confirm`) ;
  3. Kodi, qui interroge le serveur toutes les 3 s avec son code secret
     (`poll`), reçoit alors **son jeton**, une seule fois.

Les demandes en attente vivent en mémoire (10 min) : un redémarrage du
backend les efface, il suffit de relancer l'appairage sur la TV.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
import secrets
import time
from dataclasses import dataclass, field

# Alphabet sans caractères ambigus à la lecture sur une TV (0/O, 1/I/L, 8/B…)
_ALPHABET = "ACDEFGHJKMNPQRTUVWXY34679"
USER_CODE_LENGTH = 6
PAIRING_TTL_SECONDS = 600
POLL_INTERVAL_SECONDS = 3
MAX_PENDING = 20  # garde-fou : pas de remplissage infini de la mémoire


def hash_token(token: str) -> str:
    """Empreinte SHA-256 du jeton (seule valeur gardée en base)."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    """Jeton d'appareil : 256 bits aléatoires, en base64 « URL-safe »."""
    return secrets.token_urlsafe(32)


def normalize_user_code(code: str) -> str:
    """« k7p-4qx » → « K7P4QX » (tirets, espaces et casse ignorés)."""
    return re.sub(r"[^A-Z0-9]", "", (code or "").upper())


# ─────────────────────────────────────────────────────────────────────────────
# Réseau local uniquement (ADR-003, décision 4)
# ─────────────────────────────────────────────────────────────────────────────


# Réseaux locaux, listés explicitement : `ipaddress.is_private` de Python
# couvre aussi des plages réservées qui ne sont pas un réseau domestique
# (documentation, 0.0.0.0/8, etc.).
_LAN_NETWORKS = tuple(
    ipaddress.ip_network(n)
    for n in (
        "10.0.0.0/8",  # RFC 1918
        "172.16.0.0/12",  # RFC 1918 (dont les réseaux Docker)
        "192.168.0.0/16",  # RFC 1918
        "127.0.0.0/8",  # boucle locale
        "169.254.0.0/16",  # lien local
        "::1/128",
        "fc00::/7",  # IPv6 locale unique
        "fe80::/10",  # IPv6 lien local
    )
)


def _is_private(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.strip())
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return any(ip.version == net.version and ip in net for net in _LAN_NETWORKS)


def is_lan_request(client_host: str | None, forwarded_for: str | None) -> bool:
    """Vrai si la requête vient du réseau local.

    On exige une adresse privée (RFC 1918, boucle locale, IPv6 locale) pour
    la connexion elle-même ET pour chaque adresse de `X-Forwarded-For` : une
    requête venue d'Internet à travers un proxy inverse porte l'adresse
    publique du client dans cet en-tête, elle est donc refusée.
    """
    if not client_host or not _is_private(client_host):
        return False
    hops = [h for h in (forwarded_for or "").split(",") if h.strip()]
    return all(_is_private(h) for h in hops)


# ─────────────────────────────────────────────────────────────────────────────
# Périmètre « TV » : ce qu'un jeton d'appareil a le droit d'appeler
# ─────────────────────────────────────────────────────────────────────────────
# Liste blanche (tout le reste est refusé) : lecture, recherche, ajout,
# sous-titres, file en lecture seule + pause/reprise, ampli, notifications
# (lecture et « marquer lu »), recommandations, flux temps réel (SSE).
# Aucune suppression, aucun nettoyage, aucune configuration (ADR-003, décision 1).
# Seule exception, bornée : annuler SA propre demande « pour ce soir » tant
# qu'elle est en cours (téléchargement retiré du client, médiathèque intacte).

_DEVICE_ALLOWED: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (method, re.compile(pattern))
    for method, pattern in (
        ("GET", r"/api/devices/me"),
        ("GET", r"/api/kodi/(dashboard|addon-status|widgets/recent|now-playing|watched-status)"),
        ("GET", r"/api/kodi/media/(lookup|recommendations|options|seasons)"),
        ("GET", r"/api/kodi/media/(movie|series|tv)/\d+/releases"),
        ("POST", r"/api/kodi/(scrobble|sync)"),
        # Fin du journal d'une session de Kodi arrêtée net (taille bornée, rien d'exécuté)
        ("POST", r"/api/kodi/crash-report"),
        # Vu / reprise partagés entre les TV (phase 4.4) : lecture et dépôt d'états
        ("GET", r"/api/kodi/watch-state"),
        ("POST", r"/api/kodi/watch-state"),
        ("GET", r"/api/kodi/series/\d+/episodes"),  # épisodes Sonarr (manquants)
        ("POST", r"/api/kodi/actions/(search|subtitles|subtitles/sync)"),
        ("POST", r"/api/kodi/media/(add|download)"),
        ("POST", r"/api/kodi/media/(movie|series|tv)/\d+/grab"),
        ("POST", r"/api/kodi/downloads/(radarr|sonarr)/\d+/(pause|resume)"),
        # Demandes « pour ce soir » : liste, annulation de SA demande (vérifié
        # côté serveur), pause / reprise / tête de file d'UN téléchargement
        ("GET", r"/api/kodi/tv-requests"),
        ("POST", r"/api/kodi/tv-requests/\d+/(cancel|retry)"),
        ("POST", r"/api/kodi/queue/[A-Za-z0-9_.\-]+/(pause|resume|top)"),
        # Écran Téléchargements (lot 3) : tableau, diagnostic, « Débloquer »
        # (import sans écrasement ou autre release ; médiathèque jamais touchée)
        ("GET", r"/api/kodi/downloads/board"),
        # Marqueurs d'épisode de Jellyfin (« Passer l'intro » sans chapitres)
        ("GET", r"/api/kodi/segments"),
        ("GET", r"/api/kodi/downloads/(radarr|sonarr)/[A-Za-z0-9_.\-]+/diagnose"),
        ("POST", r"/api/kodi/downloads/(radarr|sonarr)/[A-Za-z0-9_.\-]+/unstick"),
        ("GET", r"/api/media(/.*)?"),
        ("GET", r"/api/downloads"),
        ("GET", r"/api/calendar(/.*)?"),
        ("GET", r"/api/notifications(/.*)?"),
        ("POST", r"/api/notifications/(\d+/read|read-all)"),
        ("GET", r"/api/recommendations(/.*)?"),
        ("GET", r"/api/events/(stream|recent)"),
        ("GET", r"/api/yamaha/(state|profiles)"),
        ("GET", r"/api/qr"),  # QR codes vers la web app (rien à modifier)
        ("GET", r"/api/cameras/snapshot/\d+"),  # photo d'une détection Eufy (pop-up)
        ("POST", r"/api/yamaha/(control|preset/apply)"),
        # Appli Android native (ADR-007) : infos de lecture, flux vidéo relayé
        # depuis Jellyfin (la clé Jellyfin reste sur le serveur), vignettes
        # de chapitres. Lecture seule.
        ("GET", r"/api/tv/play/(movie/\d+|episode/\d+/\d+/\d+)"),
        ("GET", r"/api/tv/stream/[0-9a-f]{32}"),
        ("GET", r"/api/tv/chapter-image/[0-9a-f]{32}/\d+"),
        ("GET", r"/api/tv/item-image/[0-9a-f]{32}"),
        ("GET", r"/api/tv/trailer/movie/\d+"),
        # Remux HLS (.m2ts, .iso…) : listes et morceaux seulement, puis arrêt
        (
            "GET",
            r"/api/tv/hls/[0-9a-f]{32}/((master|main)\.m3u8|hls1/[A-Za-z0-9_]+/-?\d+\.(mp4|m4s|ts))",
        ),
        ("POST", r"/api/tv/hls/[0-9a-f]{32}/stop"),
        ("GET", r"/api/tv/series/\d+/season/\d+"),  # épisodes Jellyfin (écran Série)
    )
)


# Périmètre « écran d'appoint » : il affiche, il ne commande rien.
_SCREEN_ALLOWED: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (method, re.compile(pattern))
    for method, pattern in (
        ("GET", r"/api/devices/me"),
        ("GET", r"/api/ambient"),
    )
)


def device_may_call(method: str, path: str, kind: str = "tv") -> bool:
    """Vrai si un jeton d'appareil (TV ou écran d'appoint) peut appeler cette route."""
    path = path.rstrip("/") or "/"
    allowed = _SCREEN_ALLOWED if kind == "screen" else _DEVICE_ALLOWED
    return any(m == method.upper() and p.fullmatch(path) for m, p in allowed)


# ─────────────────────────────────────────────────────────────────────────────
# Demandes d'appairage en attente (mémoire)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PendingPairing:
    device_code: str
    user_code: str
    platform: str
    ip: str
    expires_at: float
    kind: str = "tv"  # « screen » : écran d'appoint (lecture seule)
    # Remplis à la validation dans la web app :
    token: str | None = None
    device: dict | None = None
    created_at: float = field(default_factory=time.monotonic)

    @property
    def expired(self) -> bool:
        return time.monotonic() > self.expires_at


class PairingStore:
    """Demandes en attente, indexées par code secret et par code court."""

    def __init__(self) -> None:
        self._by_device_code: dict[str, PendingPairing] = {}

    def _purge(self) -> None:
        for code in [c for c, p in self._by_device_code.items() if p.expired]:
            del self._by_device_code[code]

    def start(self, platform: str, ip: str, kind: str = "tv") -> PendingPairing:
        self._purge()
        if len(self._by_device_code) >= MAX_PENDING:
            raise OverflowError("Trop de demandes d'appairage en attente")
        used = {p.user_code for p in self._by_device_code.values()}
        while True:
            user_code = "".join(secrets.choice(_ALPHABET) for _ in range(USER_CODE_LENGTH))
            if user_code not in used:
                break
        pending = PendingPairing(
            device_code=secrets.token_urlsafe(32),
            user_code=user_code,
            platform=(platform or "")[:100],
            kind=kind if kind in ("tv", "screen") else "tv",
            ip=ip,
            expires_at=time.monotonic() + PAIRING_TTL_SECONDS,
        )
        self._by_device_code[pending.device_code] = pending
        return pending

    def by_user_code(self, user_code: str) -> PendingPairing | None:
        self._purge()
        code = normalize_user_code(user_code)
        return next((p for p in self._by_device_code.values() if p.user_code == code), None)

    def by_device_code(self, device_code: str) -> PendingPairing | None:
        self._purge()
        return self._by_device_code.get(device_code or "")

    def consume(self, device_code: str) -> None:
        """Le jeton a été remis à Kodi : la demande disparaît (usage unique)."""
        self._by_device_code.pop(device_code, None)

    def clear(self) -> None:
        self._by_device_code.clear()


pairings = PairingStore()


def qr_png(data: str, scale: int = 10) -> bytes:
    """QR code en PNG (noir sur blanc, marge réglementaire de 4 modules)."""
    import io

    import segno  # import local : seul cet appel en a besoin

    buffer = io.BytesIO()
    segno.make(data, error="m").save(buffer, kind="png", scale=scale, border=4)
    return buffer.getvalue()
