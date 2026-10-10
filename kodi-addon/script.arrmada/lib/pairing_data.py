# -*- coding: utf-8 -*-
"""Appairage (ADR-003 § 4) : logique pure, sans Kodi (testée en CI).

Le déroulé côté TV :
  1. `start` → un code court (« K7P4QX ») à afficher + un code secret ;
  2. toutes les `interval` secondes, `poll` avec le code secret ;
  3. dès que le code est validé dans la web app, `poll` renvoie le jeton
     de l'appareil : on l'enregistre, l'appairage est fini.
"""

from __future__ import annotations

# Plateformes reconnues par Kodi (System.Platform.*), dans l'ordre de test
PLATFORMS = (
    ("Android", "Android"),
    ("Linux.RaspberryPi", "Raspberry Pi"),
    ("Linux", "Linux"),
    ("Windows", "Windows"),
    ("OSX", "macOS"),
    ("IOS", "iOS"),
    ("TVOS", "tvOS"),
)


def format_code(code: str) -> str:
    """« K7P4QX » → « K7P 4QX » : deux groupes de 3, plus faciles à recopier."""
    code = (code or "").strip().upper()
    return f"{code[:3]} {code[3:]}" if len(code) == 6 else code


def code_tiles(code: str) -> list[str]:
    """Un caractère par case affichée à l'écran (6 cases)."""
    return list((code or "").strip().upper()[:6].ljust(6))


def platform_label(build_version: str, platform: str) -> str:
    """« Kodi 21.1 · Android » (envoyé au serveur, affiché dans la web app).

    `build_version` = System.BuildVersion, ex. « 21.1 (21.1.0) Git:… ».
    """
    version = (build_version or "").split(" ")[0].strip()
    label = f"Kodi {version}" if version else "Kodi"
    return f"{label} · {platform}" if platform else label


def fmt_countdown(seconds: float) -> str:
    """Temps restant avant expiration du code : 582 → « 9:42 »."""
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def web_hint(verification_url: str) -> str:
    """Adresse à taper sans le code : « http://192.168.2.3:3420/settings/kodi »."""
    return (verification_url or "").split("?")[0]


def poll_outcome(response: dict) -> tuple[str, str]:
    """Interprète la réponse de /pair/poll : (état, message).

    États : « pending » (on continue), « ok » (jeton reçu), « expired »
    (code périmé, en demander un nouveau), « error » (serveur injoignable…).
    """
    if not isinstance(response, dict):
        return "error", "Réponse inattendue du serveur"
    if response.get("status") == "ok" and response.get("token"):
        return "ok", ""
    if response.get("status") == "pending":
        return "pending", ""
    if response.get("code") == 410:
        return "expired", "Ce code a expiré"
    return "error", response.get("message") or "Serveur ArrMada injoignable"


def device_summary(device: dict) -> str:
    """« Shield Salon · Salle de cinéma · Yamaha RX-A2080 » (écran de fin)."""
    rooms = {"salon": "Salon", "cinema": "Salle de cinéma"}
    parts = [
        device.get("name") or "",
        rooms.get(device.get("room") or "", ""),
        device.get("avr_name") or "",
    ]
    return " · ".join(p for p in parts if p)


# ─────────────────────────────────────────────────────────────────────────────
# Migration : ancien mot de passe → appairage (phase 3)
# ─────────────────────────────────────────────────────────────────────────────


def migration_room(room_setting: str) -> str:
    """Pièce de l'ancien réglage « Profil de la pièce » (cinema | salon)."""
    value = (room_setting or "").strip().lower()
    return value if value in ("salon", "cinema") else "salon"


def migration_confirm_outcome(response) -> str:
    """Après la validation du code avec le mot de passe : ok | refused | retry.

    refused : mot de passe refusé (401/403) ou demande invalide (422) ;
    réessayer ne changera rien, la TV devra être appairée à la main.
    retry : serveur injoignable ou erreur passagère, on réessaiera.
    """
    if not isinstance(response, dict):
        return "retry"
    if response.get("status") == "error":
        return "refused" if response.get("code") in (401, 403, 422) else "retry"
    return "ok"
