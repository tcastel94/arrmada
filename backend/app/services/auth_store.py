"""Admin password and JWT secret storage (zero-config first run).

Everything lives in the data directory (``settings.DATA_DIR``), next to the
Fernet key, so a single volume backs up the whole instance:

  - ``.jwt_secret``     random 64-byte secret used to sign session tokens,
                        generated on first start (or ``JWT_SECRET_KEY``).
  - ``.admin_password`` scrypt hash of the admin password, written by the
                        setup wizard, the Settings page or ``app.cli``.

Legacy mode: when no hash file exists but ``ARRMADA_AUTH_SECRET`` is set to
a real value (not one of the shipped placeholders), that plaintext value is
still accepted so existing installs keep working. Placeholders are refused:
an instance with no password is "unclaimed" and the UI asks to create one.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from pathlib import Path

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Values shipped in older .env.example / docker-compose.yml: never valid.
PLACEHOLDER_SECRETS = frozenset({"", "changeme", "changeme_use_a_strong_password"})

MIN_PASSWORD_LENGTH = 8

# scrypt cost (n=2^15, r=8, p=1 ≈ 32 MB RAM, ~50 ms): fine for a single
# admin login rate-limited to 5/min, and within OpenSSL's default maxmem.
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024

_jwt_secret: str | None = None


def _data_dir() -> Path:
    path = Path(settings.DATA_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _password_file() -> Path:
    return _data_dir() / ".admin_password"


def _write_private(path: Path, content: str) -> None:
    """Write a file readable by its owner only, atomically (tmp + rename)."""
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    os.replace(tmp, path)


# ── JWT secret ────────────────────────────────────────────────
def jwt_secret() -> str:
    """Return the JWT signing secret, generating it on first call."""
    global _jwt_secret
    if _jwt_secret:
        return _jwt_secret

    if settings.JWT_SECRET_KEY:
        _jwt_secret = settings.JWT_SECRET_KEY
        return _jwt_secret

    key_file = _data_dir() / ".jwt_secret"
    if key_file.exists():
        _jwt_secret = key_file.read_text(encoding="utf-8").strip()
    if not _jwt_secret:
        _jwt_secret = secrets.token_urlsafe(64)
        _write_private(key_file, _jwt_secret)
        logger.info("Generated a new JWT secret in %s", key_file)
    return _jwt_secret


# ── Admin password ────────────────────────────────────────────
def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        maxmem=_SCRYPT_MAXMEM,
    )


def _legacy_env_password() -> str | None:
    value = settings.ARRMADA_AUTH_SECRET
    return None if value in PLACEHOLDER_SECRETS else value


def password_source() -> str:
    """Where the admin password comes from: ``file``, ``env`` or ``none``."""
    if _password_file().exists():
        return "file"
    if _legacy_env_password():
        return "env"
    return "none"


def is_password_set() -> bool:
    """True once the instance has an admin password (it is "claimed")."""
    return password_source() != "none"


def set_password(password: str) -> None:
    """Hash and store a new admin password (replaces any previous one)."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    salt = secrets.token_bytes(16)
    digest = _hash(password, salt)
    salt_b64 = base64.b64encode(salt).decode()
    digest_b64 = base64.b64encode(digest).decode()
    line = f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt_b64}${digest_b64}"
    _write_private(_password_file(), line + "\n")
    logger.info("Admin password updated")


def clear_password() -> None:
    """Delete the stored hash (the instance becomes unclaimed again)."""
    _password_file().unlink(missing_ok=True)


def verify_password(password: str) -> bool:
    """Check a login attempt, in constant time."""
    pw_file = _password_file()
    if pw_file.exists():
        try:
            algo, n, r, p, salt_b64, digest_b64 = (
                pw_file.read_text(encoding="utf-8").strip().split("$")
            )
            if algo != "scrypt":
                raise ValueError(algo)
            expected = base64.b64decode(digest_b64)
            actual = hashlib.scrypt(
                password.encode("utf-8"),
                salt=base64.b64decode(salt_b64),
                n=int(n),
                r=int(r),
                p=int(p),
                maxmem=_SCRYPT_MAXMEM,
            )
        except ValueError:
            logger.error("Unreadable password file %s — refusing login", pw_file)
            return False
        return hmac.compare_digest(actual, expected)

    legacy = _legacy_env_password()
    if legacy:
        return hmac.compare_digest(password.encode("utf-8"), legacy.encode("utf-8"))
    return False
