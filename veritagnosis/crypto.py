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


# crypto

VERSION = b"\x01"       # lets the format change later without breaking old rows
NONCE_BYTES = 12        # 96 bits, the GCM standard


class DecryptionError(Exception):
    """Raised when a stored value fails authentication — wrong key, or tampering."""


@lru_cache(maxsize=1)
def _aes() -> AESGCM:
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
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
    except Exception:
        return False
    return bool(raw) and raw[:1] == VERSION


def blind_index(value: str, context: str) -> str:
    mac = hmac.new(_index_secret(), f"{context}\x00{value}".encode(), hashlib.sha256)
    return base64.urlsafe_b64encode(mac.digest()[:16]).decode("ascii")


class Encrypted(TypeDecorator):

    impl = String
    cache_ok = True

    def __init__(self, context: str, *args, legacy_plaintext: bool = False,
                 **kwargs):
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


# passwords

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
    try:
        _hasher.verify(_DUMMY_HASH, "not-the-password")
    except Exception:
        pass


_DUMMY_HASH = _hasher.hash("dummy-password-for-constant-time-login")


def problems(password: str) -> list[str]:
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


