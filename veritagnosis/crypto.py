"""
Secrets at rest: AES-256-GCM field encryption for sensitive columns, and
Argon2id password hashing.

Deliberately free of any models import. models.py needs Encrypted to define
its columns, so anything this module imports is imported before the tables
exist — which is why login and sessions live in security.py instead, and not
a stylistic preference: merging the two produces a circular import.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from functools import lru_cache
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import String, TypeDecorator
from veritagnosis import config
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from starlette.datastructures import MutableHeaders


# ====================================================================
# crypto
# ====================================================================

VERSION = b"\x01"       # lets the format change later without breaking old rows
NONCE_BYTES = 12        # 96 bits, the GCM standard


class DecryptionError(Exception):
    """Raised when a stored value fails authentication — wrong key, or tampering."""


@lru_cache(maxsize=1)
def _aes() -> AESGCM:
    """Derive a 256-bit AES key from the configured secret via HKDF.

    HKDF rather than using the env value directly: it guarantees a uniformly
    random 32 bytes regardless of how the secret was generated, and the `info`
    string domain-separates this key from the blind-index key even if someone
    misconfigures both to the same secret.
    """
    key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None,
        info=b"veritagnosis:field-encryption:v1",
    ).derive(config.field_key().encode())
    return AESGCM(key)


@lru_cache(maxsize=1)
def _index_secret() -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None,
        info=b"veritagnosis:blind-index:v1",
    ).derive(config.index_key().encode())


@lru_cache(maxsize=1)
def _code_secret() -> bytes:
    """Key for MACing short numeric codes. Domain-separated from the others."""
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None,
        info=b"veritagnosis:login-code:v1",
    ).derive(config.index_key().encode())


def code_mac(code: str, context: str) -> str:
    """Keyed hash for a six-digit login code.

    A plain SHA-256 is the right tool for a 256-bit session token and the wrong
    one for a six-digit code. Six digits is a million possibilities, which a
    laptop exhausts against an unkeyed hash in well under a second — so a
    database leak would hand an attacker every live code in it.

    Keying the hash removes the offline attack: without the server's secret
    there is nothing to grind against. The `context` binds the MAC to one
    challenge, so a code minted for one login cannot be replayed against
    another even when the same six digits come up twice.
    """
    return hmac.new(_code_secret(),
                    f"{context}|{code}".encode(), hashlib.sha256).hexdigest()


def encrypt(plaintext: str, context: str) -> str:
    """Encrypt one value. `context` is the column path, e.g. "user.gender"."""
    if plaintext is None:
        raise ValueError("encrypt() called with None; let the column stay NULL instead")
    import os
    nonce = os.urandom(NONCE_BYTES)
    ct = _aes().encrypt(nonce, plaintext.encode("utf-8"), context.encode())
    return base64.urlsafe_b64encode(VERSION + nonce + ct).decode("ascii")


def decrypt(token: str, context: str) -> str:
    """Decrypt one value, verifying it belongs to this column."""
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
    except Exception as exc:
        raise DecryptionError("stored value is not valid base64") from exc
    if not raw or raw[:1] != VERSION:
        raise DecryptionError("unknown ciphertext version")
    nonce, ct = raw[1:1 + NONCE_BYTES], raw[1 + NONCE_BYTES:]
    try:
        return _aes().decrypt(nonce, ct, context.encode()).decode("utf-8")
    except Exception as exc:
        raise DecryptionError(
            "value failed authentication — wrong key, wrong column, or tampering"
        ) from exc


def looks_encrypted(token: str) -> bool:
    """True if this value carries our ciphertext envelope.

    Used to tell a value this app encrypted from one written before the column
    was encrypted at all. It deliberately checks only the envelope, not the
    authentication tag: a value that has the envelope but fails to authenticate
    is a wrong key or tampering, and that must still raise rather than be
    mistaken for legacy data.
    """
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
    except Exception:
        return False
    return bool(raw) and raw[:1] == VERSION


def blind_index(value: str, context: str) -> str:
    """
    A deterministic, non-reversible token for equality lookups on an encrypted
    column. Encrypted values differ every time (fresh nonce), so
    `WHERE email = ?` cannot work; `WHERE email_bidx = ?` can.

    Trade-off, stated plainly: because it is deterministic, equal plaintexts
    produce equal indexes. That leaks which rows share a value, and for a
    low-cardinality column (gender, a 1-10 rating) an attacker who can guess the
    small set of possible inputs can match them by computing the HMAC of each
    guess. So: use a blind index only on high-cardinality lookup columns like
    username or email, never on gender or age.
    """
    mac = hmac.new(_index_secret(), f"{context}\x00{value}".encode(), hashlib.sha256)
    return base64.urlsafe_b64encode(mac.digest()[:16]).decode("ascii")


class Encrypted(TypeDecorator):
    """
    A SQLAlchemy column type that encrypts on write and decrypts on read, so
    models declare intent once and no call site can forget:

        gpa: str | None = Field(sa_column=Column(Encrypted("user.gpa")))

    The database only ever sees ciphertext.
    """

    impl = String
    cache_ok = True

    def __init__(self, context: str, *args, legacy_plaintext: bool = False,
                 **kwargs):
        """
        `legacy_plaintext` is for a column that was added unencrypted and
        encrypted later, where databases in the wild still hold rows written
        before the change. Reading one of those with the plain decryptor raises
        DecryptionError, which on a live app means a screen that simply will
        not open.

        With the flag set, a value that does not carry the ciphertext envelope
        is passed through as the plaintext it is, so the screen opens. A value
        that *does* carry the envelope is decrypted strictly as always, so a
        wrong key or a tampered row still fails loudly.

        Note what this does NOT do: it does not encrypt the old rows. They are
        only rewritten when something actually changes the value, because
        SQLAlchemy issues no UPDATE for a field reassigned to what it already
        held — so a student who opens the screen and saves without editing
        leaves their row in the clear. Run
        `python scripts/manage.py encrypt-profiles` to convert them all; until
        then, assume any pre-existing row is still plaintext on disk.

        Do not set this on a column that was encrypted from the start. There,
        an unreadable value is a real problem and should say so.
        """
        self.context = context
        self.legacy_plaintext = legacy_plaintext
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        return None if value is None else encrypt(str(value), self.context)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if self.legacy_plaintext and not looks_encrypted(value):
            return value
        return decrypt(value, self.context)


# ====================================================================
# passwords
# ====================================================================

_hasher = PasswordHasher(
    time_cost=2,          # iterations
    memory_cost=19 * 1024,  # 19 MiB, in KiB
    parallelism=1,
    hash_len=32,
    salt_len=16,
    type=Type.ID,         # Argon2id: hybrid, resists both side-channel and GPU attacks
)

# argon2-cffi salts every hash, so identical passwords produce different
# strings. Nothing else in the codebase should ever touch a raw password.

MIN_LENGTH = 8
MAX_LENGTH = 128  # bound the input: hashing an unbounded string is a DoS vector

# What counts as a symbol: everything printable that is not a letter, a digit
# or a space. Spelling it out beats `not c.isalnum()`, which would count a
# space, an accented letter or an emoji as a symbol and let "my password "
# through on a technicality.
_SYMBOLS = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")

# Deliberately tiny. A real deployment should check against a breached-password
# corpus (e.g. the Pwned Passwords k-anonymity API) instead of a hardcoded list.
_OBVIOUS = {
    "password", "password1", "passw0rd", "12345678910", "qwertyuiop",
    "veritagnosis", "letmein123", "iloveyou1", "admin12345",
}


def hash_password(password: str) -> str:
    """Returns a self-describing hash string: algorithm, parameters, salt, digest."""
    if len(password) > MAX_LENGTH:
        raise ValueError(f"password longer than {MAX_LENGTH} characters")
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> tuple[bool, str | None]:
    """
    Returns (ok, new_hash). `new_hash` is non-None when the stored hash used
    outdated parameters and should be replaced — write it back on a successful
    login so the database strengthens itself over time.

    Never raises on a wrong password: callers get False, so a caller cannot
    accidentally leak "user exists" through an exception path.
    """
    if len(password) > MAX_LENGTH:
        return False, None
    try:
        _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False, None
    if _hasher.check_needs_rehash(stored_hash):
        return True, _hasher.hash(password)
    return True, None


def dummy_verify() -> None:
    """Burn the same CPU/memory as a real verification.

    Call this when a username does not exist. Without it, a missing user returns
    in microseconds and a real user takes ~50ms, which lets anyone enumerate
    valid usernames with a stopwatch.
    """
    try:
        _hasher.verify(_DUMMY_HASH, "not-the-password")
    except Exception:
        pass


_DUMMY_HASH = _hasher.hash("dummy-password-for-constant-time-login")


def problems(password: str) -> list[str]:
    """Plain-language list of what is still missing. Empty list means acceptable.

    Five rules, checked in the order someone would fix them: length first,
    then the four character classes, then the blocklist. Each item completes
    the sentence "Password needs ...", so the screen can print the list back
    without rewording it.

    This is the only password policy in the program. Both the signup screen and
    the change-password screen call it, so a rule added here is enforced in
    both places and cannot drift between them.
    """
    out: list[str] = []
    if len(password) < MIN_LENGTH:
        out.append(f"at least {MIN_LENGTH} characters ({len(password)} so far)")
    if not any(c.isupper() for c in password):
        out.append("a capital letter")
    if not any(c.islower() for c in password):
        out.append("a lowercase letter")
    if not any(c.isdigit() for c in password):
        out.append("a number")
    if not any(c in _SYMBOLS for c in password):
        out.append("a symbol, like ! or ?")
    if password.lower() in _OBVIOUS:
        out.append("something less guessable")
    if len(password) > MAX_LENGTH:
        out.append(f"no more than {MAX_LENGTH} characters")
    return out


