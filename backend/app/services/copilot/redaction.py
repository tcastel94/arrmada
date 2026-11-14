"""Masquage des secrets dans ce que le copilote envoie au modèle.

Les résultats d'outils quittent le réseau local (API Anthropic). Tout ce qui
ressemble à un secret est remplacé par ``***`` AVANT l'envoi, par trois filets
successifs, du plus sûr au plus large :

1. les secrets connus (clés API des services enregistrés, clés du ``.env``),
   remplacés où qu'ils apparaissent, même au milieu d'une ligne de journal ;
2. les champs dont le NOM désigne un secret (``apiKey``, ``password``…), y
   compris la forme « liste de champs » des *arr
   (``{"name": "apiKey", "value": "…"}``) ;
3. les motifs ``cle=valeur`` dans du texte libre (URL d'indexeur avec
   ``apikey=``, ``passkey=``…) et les identifiants d'une URL (``user:pass@``).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

MASK = "***"

# Un secret connu plus court que ça n'est pas remplacé à l'aveugle : « 1234 »
# se retrouverait masqué dans un port, une taille, une année…
MIN_KNOWN_SECRET_LENGTH = 6

_SECRET_NAME = (
    r"(?:api|client|private|access|license)[_-]?key|apikey|x-api-key|pass(?:word|wd|key)|pwd|secret|token|authorization"
    r"|auth[_-]?key|rss[_-]?key|torrent[_-]?pass|cookie|credential"
)
_SECRET_NAME_RE = re.compile(_SECRET_NAME, re.IGNORECASE)

# apikey=XXXX · "token": "XXXX" · passkey: XXXX (le séparateur est gardé tel quel)
_KEY_VALUE_RE = re.compile(
    rf"(\b(?:{_SECRET_NAME})\b[\"']?\s*[=:]\s*[\"']?)([^\s&\"',;<>]+)",
    re.IGNORECASE,
)
# http://utilisateur:motdepasse@hote
_URL_CREDENTIALS_RE = re.compile(r"(://[^/\s:@]+:)([^@\s/]+)(@)")

# Champs « provider » des *arr marqués secrets par l'application elle-même.
_PRIVATE_FIELD_KINDS = {"password", "apikey"}


def is_secret_name(name: Any) -> bool:
    """Vrai si un nom de champ désigne un secret (``apiKey``, ``Password``…)."""
    return isinstance(name, str) and bool(_SECRET_NAME_RE.search(name))


def _mask_value(value: Any) -> Any:
    """Masque une valeur secrète ; une valeur vide reste vide (« non renseigné » est utile)."""
    if value is None or value == "" or isinstance(value, bool):
        return value
    return MASK


class Redactor:
    """Masque les secrets d'une structure JSON ou d'un texte."""

    def __init__(self, known_secrets: Iterable[str] = ()) -> None:
        # Les plus longs d'abord : un secret inclus dans un autre ne laisse pas de reste.
        self._known = sorted(
            {s for s in known_secrets if s and len(s) >= MIN_KNOWN_SECRET_LENGTH},
            key=len,
            reverse=True,
        )

    def text(self, value: str) -> str:
        """Masque les secrets d'un texte libre (ligne de journal, URL…)."""
        for secret in self._known:
            if secret in value:
                value = value.replace(secret, MASK)
        value = _URL_CREDENTIALS_RE.sub(rf"\1{MASK}\3", value)
        return _KEY_VALUE_RE.sub(rf"\1{MASK}", value)

    def data(self, value: Any) -> Any:
        """Copie d'une structure JSON, secrets masqués."""
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, list | tuple):
            return [self.data(item) for item in value]
        if not isinstance(value, dict):
            return value

        # Champ d'un fournisseur *arr : {"name": "apiKey", "value": "…", "privacy": "apiKey"}
        if "value" in value and (
            is_secret_name(value.get("name"))
            or str(value.get("privacy", "")).lower() in _PRIVATE_FIELD_KINDS
        ):
            return {k: (_mask_value(v) if k == "value" else self.data(v)) for k, v in value.items()}

        out: dict[str, Any] = {}
        for key, item in value.items():
            if is_secret_name(key) and not isinstance(item, dict | list):
                out[key] = _mask_value(item)
            else:
                out[key] = self.data(item)
        return out
