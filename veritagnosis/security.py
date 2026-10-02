"""
Who you are and what you did: sessions, login, the audit trail, and the
response headers the browser is told to enforce.

Depends on models; crypto deliberately does not (see crypto.py).
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import timedelta

from sqlmodel import Session, select
from starlette.datastructures import MutableHeaders

from veritagnosis import config
from veritagnosis import crypto
from veritagnosis.crypto import blind_index
from veritagnosis import crypto as passwords
from veritagnosis.models import (AuditLog, AuthSession, EmailToken,
                                 LoginChallenge, User, utcnow)


GENERIC_LOGIN_ERROR = "That username and password combination doesn't match."


def _hash_token(token: str) -> str:
    """Plain SHA-256, not Argon2, deliberately.

    Slow hashing exists to make guessing *low-entropy* human passwords
    expensive. A 256-bit random token has nothing to guess, and every request
    would pay the cost. Hashing it at all is so a database leak cannot be
    replayed."""
    return hashlib.sha256(token.encode()).hexdigest()


# --------------------------------------------------------------- registration
class RegistrationError(Exception):
    pass


# A deliberately permissive address check. The real test of an address is
# whether a code sent to it comes back, which is exactly what signup now does —
# so this only needs to catch typing errors, not adjudicate RFC 5322.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+$")


def register(session: Session, username: str, password: str, *,
             email: str | None = None, age: str | None = None,
             gender: str | None = None) -> User:
    username = username.strip()
    if not 3 <= len(username) <= 32:
        raise RegistrationError("Username must be between 3 and 32 characters.")
    if not username.replace("_", "").replace("-", "").isalnum():
        raise RegistrationError("Username can use letters, numbers, - and _ only.")

    problems = passwords.problems(password)
    if problems:
        raise RegistrationError("Password needs " + " and ".join(problems) + ".")

    # Signing in always needs a code, and a code needs somewhere to go. An
    # account without an address could be created and then never entered, so
    # the address is required here rather than discovered at the first login.
    email = (email or "").strip()
    if not email:
        raise RegistrationError(
            "An email address is required — every sign-in sends a code to it.")
    if len(email) > 254 or not _EMAIL_RE.match(email):
        raise RegistrationError("That email address doesn't look right.")

    if session.exec(select(User).where(
            User.email_bidx == blind_index(email.lower(), "user.email"))).first():
        # Deliberately not "that address is registered": the blind index makes
        # this check possible without decrypting, and the wording keeps it from
        # becoming a way to ask whether a given person has an account.
        raise RegistrationError(
            "That email address can't be used for a new account.")

    if session.exec(select(User).where(User.username == username)).first():
        # Signup is the one place enumeration cannot be avoided — the user has
        # to be told the name is taken. Login stays generic to compensate.
        raise RegistrationError("That username is taken.")

    user = User(
        username=username,
        password_hash=passwords.hash_password(password),
        email=email,
        email_bidx=blind_index(email.lower(), "user.email"),
        age=age,
        gender=gender,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    record(session, "register", user_id=user.id)
    session.commit()
    return user
# --------------------------------------------------------------------- login
#
# Two factors, every time.
#
# The old flow verified an email address once, set a flag, and from then on a
# password alone opened the account. That is email confirmation, not two-factor
# authentication: after day one there was exactly one secret between a stranger
# and a student's essays, and it was a secret the student very likely reused
# somewhere that has since been breached.
#
# Now a correct password is never, on its own, a session. It buys a challenge —
# a row that knows which account is half-way in and nothing else — and the
# session is minted only when the code sent to the registered address comes
# back. `login()` therefore has no success path that returns a token. There is
# no flag anywhere that can switch this off, because a second factor you can
# turn off is a second factor an attacker can turn off.

CHALLENGE_TTL_MINUTES = 10
MAX_CODE_ATTEMPTS = 5


class SecondFactorRequired(PermissionError):
    """The password was right. Now prove you can read the registered inbox."""

    def __init__(self, challenge: str, code: str, email: str | None, user_id: int):
        super().__init__("We emailed you a six-digit code.")
        self.challenge = challenge        # opaque handle, for the browser
        # The code travels on the exception because the caller has to put it in
        # an email. It is a server-side control-flow object and is never
        # serialised to the client — unlike a State var, which would be.
        self.code = code
        self.email = email or ""          # for the server to address the mail
        self.user_id = user_id


# Older name, kept so nothing that still imports it breaks. It always meant
# "this login is not finished yet", which is now true of every login.
EmailNotVerified = SecondFactorRequired


def begin_challenge(session: Session, user: User, *,
                    user_agent: str | None = None) -> tuple[str, str]:
    """Open a second-factor challenge. Returns (handle, code).

    The handle goes to the browser and the code goes to the inbox, and neither
    is any use without the other. Any earlier challenge for this user is
    retired first, so a code read over someone's shoulder yesterday is dead.
    """
    for old in session.exec(
        select(LoginChallenge).where(LoginChallenge.user_id == user.id,
                                     LoginChallenge.used == False)  # noqa: E712
    ).all():
        old.used = True
        session.add(old)

    handle = secrets.token_urlsafe(32)            # 256 bits from the OS CSPRNG
    handle_hash = _hash_token(handle)
    code = f"{secrets.randbelow(1_000_000):06d}"  # CSPRNG, not random.randint

    session.add(LoginChallenge(
        user_id=user.id,
        handle_hash=handle_hash,
        # Keyed, and bound to this challenge: see crypto.code_mac.
        code_hash=crypto.code_mac(code, handle_hash),
        expires_at=utcnow() + timedelta(minutes=CHALLENGE_TTL_MINUTES),
        user_agent=(user_agent or "")[:120] or None,
    ))
    session.commit()
    return handle, code


def login(session: Session, username: str, password: str, *,
          user_agent: str | None = None) -> tuple[str, User]:
    """Check the password and open a second-factor challenge.

    Never returns a session. On success it raises SecondFactorRequired, which
    carries the challenge handle; the caller mails the code and sends the user
    to the verify step. Every other failure raises PermissionError with the
    same generic message, so nothing here reveals which usernames exist.
    """
    user = session.exec(select(User).where(User.username == username.strip())).first()

    if user is None:
        # Same work as a real verification, so response time does not reveal
        # whether the account exists.
        passwords.dummy_verify()
        raise PermissionError(GENERIC_LOGIN_ERROR)

    if user.is_locked():
        record(session, "login_locked", user_id=user.id, ok=False)
        session.commit()
        mins = int((user.locked_until - utcnow()).total_seconds() // 60) + 1
        raise PermissionError(f"Too many attempts. Try again in {mins} minutes.")

    if not user.is_active:
        passwords.dummy_verify()
        raise PermissionError(GENERIC_LOGIN_ERROR)

    ok, new_hash = passwords.verify_password(user.password_hash, password)
    if not ok:
        user.failed_logins += 1
        if user.failed_logins >= config.MAX_FAILED_LOGINS:
            user.locked_until = utcnow() + timedelta(minutes=config.LOCKOUT_MINUTES)
            user.failed_logins = 0
        session.add(user)
        record(session, "login", user_id=user.id, ok=False)
        session.commit()
        raise PermissionError(GENERIC_LOGIN_ERROR)

    # An account with no registered address has no second factor and therefore
    # no way in. Registration refuses to create one; this is the guard for rows
    # that predate that rule.
    if not user.email:
        record(session, "login", user_id=user.id, ok=False,
               detail="no address for second factor")
        session.commit()
        raise PermissionError(
            "This account has no email address on it, so we cannot send a "
            "sign-in code. Please make a new account.")

    # The password was right. Upgrade the hash if the cost parameters have
    # since been raised, and clear the failure counter — but issue no session.
    if new_hash:
        user.password_hash = new_hash
    user.failed_logins = 0
    user.locked_until = None
    session.add(user)

    handle, code = begin_challenge(session, user, user_agent=user_agent)
    record(session, "login_password_ok", user_id=user.id)
    session.commit()
    raise SecondFactorRequired(handle, code, user.email, user.id)


def complete_login(session: Session, handle: str, code: str, *,
                   user_agent: str | None = None) -> tuple[str, User]:
    """Second step. Returns (raw_token, user) — the only place a session is made.

    Every failure says the same thing. Distinguishing "expired" from "wrong"
    would tell someone holding a stolen handle whether they were close.
    """
    bad = PermissionError("That code isn't right, or it has expired. "
                          "Sign in again for a fresh one.")
    if not handle or not code:
        raise bad

    row = session.exec(
        select(LoginChallenge).where(
            LoginChallenge.handle_hash == _hash_token(handle))
    ).first()
    if row is None or not row.is_live():
        raise bad

    row.attempts += 1
    # compare_digest, not ==, so the comparison cannot be timed digit by digit.
    ok = hmac.compare_digest(row.code_hash, crypto.code_mac(code, row.handle_hash))
    if not ok:
        session.add(row)
        record(session, "second_factor", user_id=row.user_id, ok=False)
        session.commit()
        raise bad

    user = session.get(User, row.user_id)
    if user is None or not user.is_active:
        row.used = True
        session.add(row)
        session.commit()
        raise bad

    row.used = True
    session.add(row)

    # Reaching here proves the address works, which is the last thing signup
    # was waiting on.
    if not user.email_verified:
        user.email_verified = True
        session.add(user)

    token = secrets.token_urlsafe(32)
    session.add(AuthSession(
        user_id=user.id,
        token_hash=_hash_token(token),
        expires_at=utcnow() + timedelta(hours=config.SESSION_TTL_HOURS),
        user_agent=(user_agent or row.user_agent or "")[:120] or None,
    ))
    record(session, "login", user_id=user.id)
    session.commit()
    return token, user


def resend_code(session: Session, handle: str) -> tuple[str, str, str] | None:
    """Retire a challenge and open a fresh one. Returns (handle, code, email).

    The handle changes too. Keeping it would mean the attempt counter survived
    a resend, so anyone could reset their five guesses by asking for a new code.
    """
    row = session.exec(
        select(LoginChallenge).where(
            LoginChallenge.handle_hash == _hash_token(handle))
    ).first()
    if row is None or row.used or row.expires_at < utcnow():
        return None
    user = session.get(User, row.user_id)
    if user is None or not user.is_active or not user.email:
        return None
    new_handle, code = begin_challenge(session, user, user_agent=row.user_agent)
    record(session, "second_factor_resend", user_id=user.id)
    session.commit()
    return new_handle, code, user.email


def challenge_email(session: Session, handle: str) -> str | None:
    """The address a live challenge was sent to, for masking on screen."""
    if not handle:
        return None
    row = session.exec(
        select(LoginChallenge).where(
            LoginChallenge.handle_hash == _hash_token(handle))
    ).first()
    if row is None or not row.is_live():
        return None
    user = session.get(User, row.user_id)
    return user.email if user else None


def session_user(session: Session, token: str | None) -> User | None:
    """Resolve a raw token to a user, or None. Refreshes the idle timer."""
    if not token:
        return None
    row = session.exec(
        select(AuthSession).where(AuthSession.token_hash == _hash_token(token))
    ).first()
    if row is None or not row.is_valid(config.SESSION_IDLE_HOURS):
        return None
    row.last_seen = utcnow()
    session.add(row)
    session.commit()
    return session.get(User, row.user_id)


def logout(session: Session, token: str | None) -> None:
    if not token:
        return
    row = session.exec(
        select(AuthSession).where(AuthSession.token_hash == _hash_token(token))
    ).first()
    if row:
        row.revoked = True          # revoke, don't delete: the row is evidence
        session.add(row)
        record(session, "logout", user_id=row.user_id)
        session.commit()


def logout_everywhere(session: Session, user_id: int) -> int:
    """Revoke every session for a user. Call after a password change."""
    rows = session.exec(
        select(AuthSession).where(AuthSession.user_id == user_id,
                                  AuthSession.revoked == False)  # noqa: E712
    ).all()
    for r in rows:
        r.revoked = True
        session.add(r)
    session.commit()
    return len(rows)


# ------------------------------------------------------------ email verifying
MAX_CODE_ATTEMPTS = 5


def issue_email_code(session: Session, user_id: int) -> str:
    """Six digits, hashed at rest, valid for 15 minutes, one live code per user."""
    for old in session.exec(
        select(EmailToken).where(EmailToken.user_id == user_id,
                                 EmailToken.used == False)  # noqa: E712
    ).all():
        old.used = True
        session.add(old)

    code = f"{secrets.randbelow(1_000_000):06d}"   # CSPRNG, not random.randint
    session.add(EmailToken(
        user_id=user_id,
        code_hash=_hash_token(code),
        expires_at=utcnow() + timedelta(minutes=15),
    ))
    session.commit()
    return code


def check_email_code(session: Session, user_id: int, code: str) -> bool:
    row = session.exec(
        select(EmailToken).where(EmailToken.user_id == user_id,
                                 EmailToken.used == False)  # noqa: E712
    ).first()
    if row is None or row.expires_at < utcnow() or row.attempts >= MAX_CODE_ATTEMPTS:
        return False

    row.attempts += 1
    # compare_digest, not ==, so the comparison cannot be timed character by
    # character.
    ok = hmac.compare_digest(row.code_hash, _hash_token(code))
    if ok:
        row.used = True
        user = session.get(User, user_id)
        if user:
            user.email_verified = True
            session.add(user)
        record(session, "email_verify", user_id=user_id)
    session.add(row)
    session.commit()
    return ok


def change_password(session: Session, user: User, old: str, new: str) -> None:
    ok, _ = passwords.verify_password(user.password_hash, old)
    if not ok:
        raise PermissionError("Current password is incorrect.")
    problems = passwords.problems(new)
    if problems:
        raise ValueError("New password needs " + " and ".join(problems) + ".")
    user.password_hash = passwords.hash_password(new)
    session.add(user)
    record(session, "password_change", user_id=user.id)
    session.commit()
    # Anyone who stole a session no longer has one.
    logout_everywhere(session, user.id)


# ====================================================================
# audit
# ====================================================================

ACTIONS = {
    "register", "login", "logout", "login_locked", "password_change",
    "email_verify", "session_expired", "data_export", "account_delete",
    # The two halves of a sign-in are recorded separately, so the log can tell
    # "someone knows this password" apart from "someone got in". A run of
    # login_password_ok with no matching login is exactly what a stolen
    # password looks like, and it is invisible if you only log the success.
    "login_password_ok", "second_factor", "second_factor_resend",
}

MAX_DETAIL = 200


def record(session: Session, action: str, *, user_id: int | None = None,
           detail: str | None = None, ok: bool = True) -> None:
    if action not in ACTIONS:
        raise ValueError(f"unknown audit action {action!r}; add it to ACTIONS")
    session.add(AuditLog(
        action=action,
        user_id=user_id,
        detail=(detail or "")[:MAX_DETAIL] or None,
        ok=ok,
    ))


# ====================================================================
# headers
# ====================================================================

CSP = "; ".join([
    "default-src 'self'",
    # Reflex inlines hydration script and Radix inlines style.
    "script-src 'self' 'unsafe-inline'",
    # fonts.googleapis.com serves the @font-face stylesheet for the five theme
    # typefaces. Omitting it here silently killed every one of them and dropped
    # the whole app to system sans — a CSP failure looks like a design change,
    # which is what makes it such an easy one to ship by accident.
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "img-src 'self' data: blob:",
    # ...and gstatic serves the actual font files that stylesheet points at.
    # Both hosts are needed; allowing only one still leaves you with no fonts.
    "font-src 'self' data: https://fonts.gstatic.com",
    # The websocket the whole app runs on.
    "connect-src 'self' ws: wss:",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
])

HEADERS = {
    "content-security-policy": CSP,
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
    "x-frame-options": "DENY",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), "
                          "interest-cohort=()",
}

HSTS = "max-age=31536000; includeSubDomains"


def security_headers(app):
    """ASGI middleware. Passed to rx.App(api_transformer=...)."""

    async def wrapped(scope, receive, send):
        if scope.get("type") != "http":
            return await app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                h = MutableHeaders(scope=message)
                for k, v in HEADERS.items():
                    if k not in h:
                        h[k] = v
                # Only meaningful on a connection that was already secure.
                if scope.get("scheme") == "https" and \
                        "strict-transport-security" not in h:
                    h["strict-transport-security"] = HSTS
            await send(message)

        await app(scope, receive, send_with_headers)

    return wrapped
