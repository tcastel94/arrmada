"""Fernet encryption for API keys stored in the database."""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet

from app.config import settings

_DATA_DIR = Path("data")
_KEY_FILE = _DATA_DIR / ".fernet_key"


def _load_or_create_key() -> bytes:
    """Load the Fernet key from config, file, or generate a new one."""
    # 1. From environment / settings
    if settings.FERNET_KEY:
        return settings.FERNET_KEY.encode()

    # 2. From persisted key file
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes().strip()

    # 3. Generate new key and persist
    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    return key


_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Lazy-initialise the Fernet cipher."""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_or_create_key())
    return _fernet


def encrypt_api_key(plain: str) -> str:
    """Encrypt an API key → returns a base64-encoded string safe for DB storage."""
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_api_key(token: str) -> str:
    """Decrypt a previously encrypted API key."""
    return _get_fernet().decrypt(token.encode()).decode()
