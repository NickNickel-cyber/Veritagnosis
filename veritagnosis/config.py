"""
Configuration and key management.

Secrets come from the environment (loaded from a local .env that is never
committed). The app refuses to start with missing or placeholder keys rather
than silently falling back to a default — a hardcoded default key is the single
most common way an otherwise-careful project leaks everything, because it ships
in the repo and every deployment shares it.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

# Where the app keeps its data and reads its .env.
#
# Normally this is the project folder — one level up from this module. It is
# overridable, and that override is not a nicety: when the app is packaged as a
# single executable, this module lives inside a temporary extraction directory
# that the operating system deletes when the process exits. Resolving the
# database path relative to __file__ there would put a student's account,
# essays and progress in a folder that is thrown away the moment they close the
# window, and the second launch would look like a brand-new install.
#
# launch.py sets VG_BASE_DIR to the directory the executable itself sits in, so
# data persists beside it.
_BASE_OVERRIDE = os.environ.get("VG_BASE_DIR", "").strip()
BASE_DIR = (Path(_BASE_OVERRIDE).resolve() if _BASE_OVERRIDE
            else Path(__file__).resolve().parent.parent)
DATA_DIR = BASE_DIR / "data"
ENV_FILE = BASE_DIR / ".env"

# encoding pinned so a .env written by another tool on Windows
# cannot take the app down with a UnicodeDecodeError.
load_dotenv(ENV_FILE, encoding="utf-8")

# Values that must never be accepted as real keys.
_PLACEHOLDERS = {"", "changeme", "CHANGEME", "your-key-here", "REPLACE_ME"}


class ConfigError(RuntimeError):
    """Raised at import time so a misconfigured app fails loudly at startup
    instead of at the first login attempt."""


def _require(name: str, min_len: int = 32) -> str:
    value = os.environ.get(name, "")
    if value in _PLACEHOLDERS:
        raise ConfigError(
            f"{name} is not set. Run:  python scripts/manage.py init-keys\n"
            f"That writes a .env with freshly generated keys. Never commit it."
        )
    if len(value) < min_len:
        raise ConfigError(
            f"{name} is too short ({len(value)} chars, need >= {min_len}). "
            f"Regenerate with: python scripts/manage.py init-keys"
        )
    return value


def generate_key() -> str:
    """A fresh URL-safe 256-bit key."""
    return secrets.token_urlsafe(32)


# --- keys -----------------------------------------------------------------
# FIELD_KEY encrypts sensitive columns (grades, scores, age, gender).
# INDEX_KEY derives blind indexes so encrypted columns stay searchable.
# They are separate so that leaking the lookup key does not decrypt content.
def field_key() -> str:
    return _require("VG_FIELD_KEY")


def index_key() -> str:
    return _require("VG_INDEX_KEY")


def db_key() -> str | None:
    """Optional whole-file SQLCipher key. Absent = plain SQLite file."""
    v = os.environ.get("VG_DB_KEY", "")
    return None if v in _PLACEHOLDERS else v


# --- database -------------------------------------------------------------
DB_PATH = DATA_DIR / "veritagnosis.db"
ENCRYPT_WHOLE_DB = os.environ.get("VG_ENCRYPT_DB", "0") == "1"

# --- session policy -------------------------------------------------------
SESSION_TTL_HOURS = int(os.environ.get("VG_SESSION_TTL_HOURS", "168"))   # 7 days
SESSION_IDLE_HOURS = int(os.environ.get("VG_SESSION_IDLE_HOURS", "24"))
MAX_FAILED_LOGINS = int(os.environ.get("VG_MAX_FAILED_LOGINS", "8"))
LOCKOUT_MINUTES = int(os.environ.get("VG_LOCKOUT_MINUTES", "15"))

# --- email (Gmail) ---
# Optional. Without these the verification code prints to the terminal instead.
SMTP_HOST = os.environ.get("VG_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("VG_SMTP_PORT", "465"))


def smtp_user() -> str:
    return os.environ.get("VG_SMTP_USER", "").strip()


def smtp_password() -> str:
    # Google shows app passwords in groups of four; people paste the spaces.
    return os.environ.get("VG_SMTP_PASSWORD", "").replace(" ", "").strip()


def mail_from_name() -> str:
    """The name a student sees in their inbox. Always the app, never a person.

    An empty or whitespace value falls back rather than passing through, so a
    blank line in .env cannot put a personal address in the From header.
    """
    return os.environ.get("VG_MAIL_FROM_NAME", "").strip() or "Veritagnosis"


# --- app ------------------------------------------------------------------
DEBUG = os.environ.get("VG_DEBUG", "0") == "1"
