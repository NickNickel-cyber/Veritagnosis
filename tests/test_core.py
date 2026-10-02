"""
Security, storage and isolation.

Encryption at rest, password hashing, sessions and the audit trail;
the schema repair that keeps older databases working; the ownership
stamp that stops one student seeing another's data; and the encoding
rules every source file has to follow.

Merged from: test_security, test_encoding, test_schema_repair, test_state_isolation.
"""
from __future__ import annotations

import os
import time
from datetime import timedelta
import pytest
from sqlmodel import Session, SQLModel, create_engine, select
import ast
import pathlib
import sqlite3
from sqlmodel import Session, SQLModel, create_engine
from veritagnosis import security as auth
from veritagnosis.states.play_state import AchievementsState
from veritagnosis.states.money_state import AidState
from veritagnosis.states.auth_state import AuthState
from veritagnosis.states.play_state import AvatarState
from veritagnosis.states.base import FeatureState
from veritagnosis.states.apply_state import EssayState
from veritagnosis.states.play_state import GrazeState
from veritagnosis.states.play_state import MeditationState
from veritagnosis.states.profile_state import ProfileState
from veritagnosis.states.apply_state import RecsState
from veritagnosis.states.apply_state import SchoolsState


# ====================================================================
# from test_security.py
# ====================================================================

os.environ.setdefault("VG_FIELD_KEY", "test-field-key-aaaaaaaaaaaaaaaaaaaaaaaa")
os.environ.setdefault("VG_INDEX_KEY", "test-index-key-bbbbbbbbbbbbbbbbbbbbbbbb")

from veritagnosis import config  # noqa: E402
from veritagnosis.models import (AuditLog, AuthSession, LoginChallenge,  # noqa: E402
                                 User, utcnow)
from veritagnosis import security as auth, crypto as passwords  # noqa: E402
from veritagnosis.crypto import (  # noqa: E402
    DecryptionError, blind_index, decrypt, encrypt,
)


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}",
                           connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s



def _register_verified(db, username="sri", password="correct-horse-42", **kw):
    """Register an account that is able to sign in.

    Every account needs an address now, because every sign-in mails a code to
    it, so the default is supplied here rather than in twenty call sites.
    """
    kw.setdefault("email", f"{username}@example.com")
    user = auth.register(db, username, password, **kw)
    db.refresh(user)
    return user


def _sign_in(db, username="sri", password="correct-horse-42"):
    """Complete BOTH factors and return (token, user).

    Also pins the rule that makes the rest of this suite meaningful: login()
    has no success path. If a future edit gives it one, every test that signs
    in fails here rather than quietly testing a single-factor app.
    """
    try:
        auth.login(db, username, password)
    except auth.SecondFactorRequired as e:
        return auth.complete_login(db, e.challenge, e.code)
    raise AssertionError("login() returned a session without a second factor")


# ------------------------------------------------------------------ passwords
def test_hash_is_argon2id_and_salted():
    a = passwords.hash_password("correct-horse-42")
    b = passwords.hash_password("correct-horse-42")
    assert a.startswith("$argon2id$")
    assert a != b, "identical passwords must not produce identical hashes"


def test_verify_accepts_right_rejects_wrong():
    h = passwords.hash_password("correct-horse-42")
    assert passwords.verify_password(h, "correct-horse-42")[0] is True
    assert passwords.verify_password(h, "correct-horse-43")[0] is False


def test_verify_never_raises_on_garbage():
    # A malformed stored hash must not crash the login path.
    assert passwords.verify_password("not-a-hash", "x") == (False, None)
    assert passwords.verify_password("", "x") == (False, None)


def test_password_length_is_bounded():
    # Unbounded input to a memory-hard hash is a denial-of-service vector.
    with pytest.raises(ValueError):
        passwords.hash_password("a" * 5000)
    assert passwords.verify_password(passwords.hash_password("ok"), "a" * 5000)[0] is False


def test_weak_passwords_are_rejected():
    assert passwords.problems("short") != []
    assert passwords.problems("password") != []
    assert passwords.problems("alphabetsonly") == ["a number or symbol"]
    assert passwords.problems("correct-horse-42") == []


# ----------------------------------------------------------------- encryption
def test_encrypt_roundtrip_and_nondeterminism():
    a = encrypt("3.92", "user.gpa")
    assert decrypt(a, "user.gpa") == "3.92"
    assert encrypt("3.92", "user.gpa") != a, "each write needs a fresh nonce"
    assert "3.92" not in a


def test_ciphertext_is_bound_to_its_column():
    token = encrypt("male", "user.gender")
    with pytest.raises(DecryptionError):
        decrypt(token, "user.gpa")   # cannot be moved between columns


def test_tampering_is_detected():
    token = encrypt("1450", "score.score")
    tampered = token[:-8] + ("A" * 8 if token[-8:] != "A" * 8 else "B" * 8)
    with pytest.raises(DecryptionError):
        decrypt(tampered, "score.score")


def test_blind_index_is_deterministic_and_domain_separated():
    assert blind_index("a@b.com", "user.email") == blind_index("a@b.com", "user.email")
    assert blind_index("a@b.com", "user.email") != blind_index("a@b.com", "other.email")
    assert "a@b.com" not in blind_index("a@b.com", "user.email")


# ------------------------------------------------------- the file on disk
def test_sensitive_values_are_not_readable_in_the_db_file(tmp_path):
    """The one that matters: open the .db as raw bytes and confirm the secrets
    are not sitting there in plaintext."""
    path = tmp_path / "leak.db"
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        auth.register(s, "leaktest", "correct-horse-42",
                      email="secret@example.com", age="17", gender="nonbinary")
        u = s.exec(select(User)).first()
        u.gpa = "3.92"
        s.add(u); s.commit()

    engine.dispose()
    raw = path.read_bytes()
    for secret in (b"secret@example.com", b"nonbinary", b"3.92", b"correct-horse-42"):
        assert secret not in raw, f"{secret!r} is readable in the database file"
    assert b"leaktest" in raw, "username is intentionally plaintext; test is wired up"


# ---------------------------------------------------------------- registration
def test_registration_rejects_bad_input(db):
    with pytest.raises(auth.RegistrationError):
        auth.register(db, "ab", "correct-horse-42")            # too short
    with pytest.raises(auth.RegistrationError):
        auth.register(db, "has space", "correct-horse-42")     # invalid chars
    with pytest.raises(auth.RegistrationError):
        auth.register(db, "okname", "short")                   # weak password


def test_duplicate_username_rejected(db):
    _register_verified(db)
    with pytest.raises(auth.RegistrationError):
        # A different address, so it is the username that collides.
        auth.register(db, "sri", "another-good-one-1", email="other@example.com")


def test_password_is_never_stored(db):
    auth.register(db, "sri", "correct-horse-42", email="a@b.com")
    u = db.exec(select(User)).first()
    assert "correct-horse-42" not in u.password_hash
    assert u.password_hash.startswith("$argon2id$")


# ---------------------------------------------------------------------- login
def test_login_success_and_failure(db):
    _register_verified(db)
    token, user = _sign_in(db)
    assert auth.session_user(db, token).id == user.id
    with pytest.raises(PermissionError):
        auth.login(db, "sri", "wrong-password-1")


def test_unknown_user_and_wrong_password_give_the_same_message(db):
    _register_verified(db)
    with pytest.raises(PermissionError) as no_user:
        auth.login(db, "nobody", "correct-horse-42")
    with pytest.raises(PermissionError) as bad_pw:
        auth.login(db, "sri", "wrong-password-1")
    assert str(no_user.value) == str(bad_pw.value) == auth.GENERIC_LOGIN_ERROR


def test_unknown_user_takes_comparable_time(db):
    """Guards the dummy_verify() call. Without it a missing user returns in
    microseconds and a real one takes ~50ms, which enumerates accounts."""
    auth.register(db, "sri", "correct-horse-42", email="a@b.com")

    def timed(name):
        t = time.perf_counter()
        try:
            auth.login(db, name, "wrong-password-1")
        except PermissionError:
            pass
        return time.perf_counter() - t

    real = min(timed("sri") for _ in range(3))
    missing = min(timed("nobody") for _ in range(3))
    assert missing > real * 0.4, f"missing={missing:.4f}s vs real={real:.4f}s"


def test_lockout_after_repeated_failures(db):
    _register_verified(db)
    for _ in range(config.MAX_FAILED_LOGINS):
        with pytest.raises(PermissionError):
            auth.login(db, "sri", "wrong-password-1")
    # Correct password now also refused, and the message says so.
    with pytest.raises(PermissionError) as e:
        auth.login(db, "sri", "correct-horse-42")
    assert "Try again in" in str(e.value)


# -------------------------------------------------------------------- sessions
def test_session_token_is_not_stored_raw(db):
    _register_verified(db)
    token, _ = _sign_in(db)
    row = db.exec(select(AuthSession)).first()
    assert row.token_hash != token
    assert token not in row.token_hash


def test_logout_revokes(db):
    _register_verified(db)
    token, _ = _sign_in(db)
    auth.logout(db, token)
    assert auth.session_user(db, token) is None


def test_expired_session_rejected(db):
    _register_verified(db)
    token, _ = _sign_in(db)
    row = db.exec(select(AuthSession)).first()
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.add(row); db.commit()
    assert auth.session_user(db, token) is None


def test_idle_session_rejected(db):
    _register_verified(db)
    token, _ = _sign_in(db)
    row = db.exec(select(AuthSession)).first()
    row.last_seen = utcnow() - timedelta(hours=config.SESSION_IDLE_HOURS + 1)
    db.add(row); db.commit()
    assert auth.session_user(db, token) is None


def test_password_change_kills_other_sessions(db):
    user = _register_verified(db)
    stolen, _ = _sign_in(db)
    auth.change_password(db, user, "correct-horse-42", "brand-new-secret-9")
    assert auth.session_user(db, stolen) is None


def test_bad_token_is_rejected(db):
    assert auth.session_user(db, None) is None
    assert auth.session_user(db, "") is None
    assert auth.session_user(db, "made-up-token") is None


# ------------------------------------------------------------ email verification
def test_email_code_single_use_and_attempt_capped(db):
    user = auth.register(db, "sri", "correct-horse-42", email="a@b.com")
    code = auth.issue_email_code(db, user.id)
    assert len(code) == 6 and code.isdigit()
    for _ in range(auth.MAX_CODE_ATTEMPTS):
        auth.check_email_code(db, user.id, "000000")
    # Attempts exhausted: even the right code is refused.
    assert auth.check_email_code(db, user.id, code) is False


def test_email_code_cannot_be_replayed(db):
    user = auth.register(db, "sri", "correct-horse-42", email="a@b.com")
    code = auth.issue_email_code(db, user.id)
    assert auth.check_email_code(db, user.id, code) is True
    assert auth.check_email_code(db, user.id, code) is False


# ----------------------------------------------------------------- audit log
def test_audit_log_holds_no_secrets(db):
    user = _register_verified(db, email="a@b.com", age="17")
    token, _ = _sign_in(db)
    with pytest.raises(PermissionError):
        auth.login(db, "sri", "wrong-password-1")
    auth.logout(db, token)

    rows = db.exec(select(AuditLog)).all()
    assert len(rows) >= 3
    blob = " ".join(f"{r.action} {r.detail or ''}" for r in rows)
    for secret in ("correct-horse-42", "wrong-password-1", token, "a@b.com", "17"):
        assert secret not in blob, f"audit log leaked {secret!r}"
    assert any(r.action == "login" and not r.ok for r in rows), "failures must be logged"


def test_audit_rejects_unknown_actions(db):
    from veritagnosis import security as audit
    with pytest.raises(ValueError):
        audit.record(db, "definitely-not-an-action")


# ------------------------------------------------------ two-factor is required
#
# The rule these defend: a password is never a session.
#
# The previous design confirmed an email address once, set email_verified, and
# from then on let the password alone straight in. That is email confirmation
# wearing the name of two-factor authentication, and the test below named
# `test_a_verified_account_still_needs_the_second_factor` is the one that stops
# it coming back — it is the exact behaviour that used to be correct.

def test_a_correct_password_creates_no_session(db):
    """The invariant. Everything else here is a detail of it."""
    _register_verified(db)
    with pytest.raises(auth.SecondFactorRequired):
        auth.login(db, "sri", "correct-horse-42")
    assert db.exec(select(AuthSession)).all() == [], (
        "a correct password minted a session without the second factor")


def test_a_verified_account_still_needs_the_second_factor(db):
    """Regression guard.

    email_verified means "this address has been proven to work", not "this
    person may skip the code". An account in that state is precisely the one
    the old code let in on a password alone.
    """
    user = _register_verified(db)
    user.email_verified = True
    db.add(user); db.commit()

    with pytest.raises(auth.SecondFactorRequired):
        auth.login(db, "sri", "correct-horse-42")
    assert db.exec(select(AuthSession)).all() == []


def test_the_code_completes_the_login(db):
    _register_verified(db)
    token, user = _sign_in(db)
    assert auth.session_user(db, token).id == user.id
    # completing it also proves the address works
    assert db.get(User, user.id).email_verified is True


def test_a_wrong_code_is_refused(db):
    _register_verified(db)
    with pytest.raises(auth.SecondFactorRequired) as e:
        auth.login(db, "sri", "correct-horse-42")
    with pytest.raises(PermissionError):
        auth.complete_login(db, e.value.challenge, "000000")
    assert db.exec(select(AuthSession)).all() == []


def test_the_code_cannot_be_replayed(db):
    _register_verified(db)
    with pytest.raises(auth.SecondFactorRequired) as e:
        auth.login(db, "sri", "correct-horse-42")
    auth.complete_login(db, e.value.challenge, e.value.code)
    with pytest.raises(PermissionError):
        auth.complete_login(db, e.value.challenge, e.value.code)


def test_the_attempt_cap_blocks_even_the_right_code(db):
    """Six digits is a million guesses. Uncapped, that is an afternoon."""
    _register_verified(db)
    with pytest.raises(auth.SecondFactorRequired) as e:
        auth.login(db, "sri", "correct-horse-42")
    for _ in range(auth.MAX_CODE_ATTEMPTS):
        with pytest.raises(PermissionError):
            auth.complete_login(db, e.value.challenge, "000000")
    with pytest.raises(PermissionError):
        auth.complete_login(db, e.value.challenge, e.value.code)


def test_an_expired_challenge_is_refused(db):
    _register_verified(db)
    with pytest.raises(auth.SecondFactorRequired) as e:
        auth.login(db, "sri", "correct-horse-42")
    row = db.exec(select(LoginChallenge)).first()
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.add(row); db.commit()
    with pytest.raises(PermissionError):
        auth.complete_login(db, e.value.challenge, e.value.code)


def test_a_code_is_bound_to_its_own_challenge(db):
    """Two live sign-ins must not accept each other's codes, even on the
    astronomically unlikely day the same six digits come up twice."""
    _register_verified(db, "amara")
    _register_verified(db, "boris")
    with pytest.raises(auth.SecondFactorRequired) as a:
        auth.login(db, "amara", "correct-horse-42")
    with pytest.raises(auth.SecondFactorRequired) as b:
        auth.login(db, "boris", "correct-horse-42")
    with pytest.raises(PermissionError):
        auth.complete_login(db, a.value.challenge, b.value.code)
    with pytest.raises(PermissionError):
        auth.complete_login(db, b.value.challenge, a.value.code)


def test_resending_retires_the_old_handle_and_its_attempts(db):
    """Otherwise 'send a new code' is a button that resets your five guesses."""
    _register_verified(db)
    with pytest.raises(auth.SecondFactorRequired) as e:
        auth.login(db, "sri", "correct-horse-42")
    old_handle, old_code = e.value.challenge, e.value.code
    for _ in range(auth.MAX_CODE_ATTEMPTS):
        with pytest.raises(PermissionError):
            auth.complete_login(db, old_handle, "000000")

    fresh = auth.resend_code(db, old_handle)
    assert fresh is not None
    new_handle, new_code, _email = fresh
    assert new_handle != old_handle

    # the old pair is dead in both directions
    with pytest.raises(PermissionError):
        auth.complete_login(db, old_handle, old_code)
    with pytest.raises(PermissionError):
        auth.complete_login(db, new_handle, old_code)
    # and the new one works
    token, _ = auth.complete_login(db, new_handle, new_code)
    assert auth.session_user(db, token).username == "sri"


def test_registration_requires_an_email(db):
    """A code needs somewhere to go. An account without one could be created
    and then never entered."""
    with pytest.raises(auth.RegistrationError):
        auth.register(db, "sri", "correct-horse-42")
    with pytest.raises(auth.RegistrationError):
        auth.register(db, "sri", "correct-horse-42", email="not-an-address")


def test_the_code_is_not_recoverable_from_the_database(db):
    """The stored value is a keyed MAC, so a leaked database yields nothing.

    A bare SHA-256 of six digits is a table of one million entries — seconds of
    work. This asserts the stored digest is not that.
    """
    import hashlib
    _register_verified(db)
    with pytest.raises(auth.SecondFactorRequired) as e:
        auth.login(db, "sri", "correct-horse-42")
    row = db.exec(select(LoginChallenge)).first()
    code = e.value.code
    assert code not in row.code_hash
    assert row.code_hash != hashlib.sha256(code.encode()).hexdigest()
    # and the whole six-digit space does not contain it under a bare hash
    space = {hashlib.sha256(f"{i:06d}".encode()).hexdigest() for i in range(1000)}
    assert row.code_hash not in space


def test_the_browser_handle_says_nothing_about_the_account(db):
    """It replaced a user id and a full email address in local storage."""
    _register_verified(db, "amara")
    with pytest.raises(auth.SecondFactorRequired) as first:
        auth.login(db, "amara", "correct-horse-42")
    with pytest.raises(auth.SecondFactorRequired) as second:
        auth.login(db, "amara", "correct-horse-42")

    handle = first.value.challenge
    assert "amara" not in handle
    assert "@" not in handle
    # Random, not an encoding of the account: the same user signing in twice
    # gets two unrelated handles. (Not asserting the id is absent as a
    # substring — a short id turns up in random base64 by chance.)
    assert first.value.challenge != second.value.challenge
    assert len(handle) >= 40

    # nor is it stored raw, so a leaked database cannot replay it
    rows = db.exec(select(LoginChallenge)).all()
    assert all(r.handle_hash != handle and handle not in r.handle_hash
               for r in rows)


def test_both_halves_of_a_sign_in_are_recorded(db):
    """A run of password-ok with no matching login is what a stolen password
    looks like, and it is invisible if only successes are logged."""
    _register_verified(db)
    with pytest.raises(auth.SecondFactorRequired) as e:
        auth.login(db, "sri", "correct-horse-42")
    with pytest.raises(PermissionError):
        auth.complete_login(db, e.value.challenge, "000000")

    actions = [r.action for r in db.exec(select(AuditLog)).all()]
    assert "login_password_ok" in actions
    assert any(r.action == "second_factor" and not r.ok
               for r in db.exec(select(AuditLog)).all())
    assert "login" not in actions, "no session was created, so none was logged"


def test_the_second_factor_is_checked_after_the_password(db):
    """A wrong password must not reveal that the account exists by returning a
    different error from a wrong username."""
    _register_verified(db)
    with pytest.raises(PermissionError) as e:
        auth.login(db, "sri", "the-wrong-password-1")
    assert not isinstance(e.value, auth.SecondFactorRequired)
    assert str(e.value) == auth.GENERIC_LOGIN_ERROR
    assert db.exec(select(LoginChallenge)).all() == []


# ----------------------------------------------------------------- demo mode
#
# With no mail server there is nowhere for a code to go, so it is shown on
# screen instead. That is a real reduction in security and the boundary around
# it is narrow: it applies ONLY when the mailer reports it is unconfigured.
# A configured mailer that fails is an outage, and leaking the code to the
# browser there would turn an outage into a vulnerability. These pin that line.

def _send(monkeypatch, *, configured, result=True, boom=False):
    """Drive AuthState._send_code against a stand-in self."""
    import asyncio, types
    from veritagnosis.states.auth_state import AuthState
    from veritagnosis import mailer

    def sender(*_a, **_k):
        if boom:
            raise mailer.MailError("smtp refused")
        return result

    monkeypatch.setattr(mailer, "is_configured", lambda: configured)
    monkeypatch.setattr(mailer, "send_verification_code", sender)
    fake = types.SimpleNamespace(demo_code="stale", emailed=None)
    asyncio.run(AuthState._send_code(fake, "a@b.com", "123456"))
    return fake


def test_the_code_is_shown_on_screen_only_when_there_is_no_mail_server(monkeypatch):
    fake = _send(monkeypatch, configured=False, result=False)
    assert fake.demo_code == "123456", (
        "with no mail configured the code has nowhere else to go")


def test_a_working_mail_server_never_puts_the_code_in_the_browser(monkeypatch):
    fake = _send(monkeypatch, configured=True, result=True)
    assert fake.demo_code == ""
    assert fake.emailed is True


def test_a_failed_send_never_puts_the_code_in_the_browser(monkeypatch):
    """An outage must not become a vulnerability."""
    fake = _send(monkeypatch, configured=True, boom=True)
    assert fake.demo_code == ""
    assert fake.emailed is False


def test_a_stale_demo_code_is_cleared_before_every_send(monkeypatch):
    """Otherwise a code from an earlier attempt lingers on screen."""
    fake = _send(monkeypatch, configured=True, result=True)
    assert fake.demo_code == "", "the previous attempt's code was left on screen"


# --------------------------------------------- profile screen, September 2026
def test_profile_data_is_encrypted_at_rest():
    """Career, major and activities are stored on the user row. If that column
    is written in the clear, anyone with the database file reads it."""
    import uuid
    from sqlalchemy import text
    from veritagnosis import db as _db
    from veritagnosis.models import User as _User

    marker = f"RoboticsCaptain{uuid.uuid4().hex[:6]}"
    with _db.get_session() as s:
        u = _User(username=f"enc_{uuid.uuid4().hex[:8]}", password_hash="x")
        u.profile_data = f'{{"career_interest": "{marker}"}}'
        s.add(u); s.commit(); s.refresh(u)
        uid = u.id

    # Read the raw bytes, bypassing the ORM's decryption.
    with _db.engine.connect() as conn:
        raw = conn.execute(
            text("SELECT profile_data FROM user WHERE id = :i"), {"i": uid}
        ).scalar()
    assert raw is not None
    assert marker not in str(raw), "profile_data was written in plaintext"

    # And it still round-trips.
    with _db.get_session() as s:
        assert marker in s.get(_User, uid).profile_data


def test_profile_free_text_is_length_capped():
    """These handlers are reachable over the websocket, so the UI's own
    choices are not a limit on what can arrive."""
    from veritagnosis.states.profile_state import MAX_FIELD, ProfileState

    class _Fake:
        career_interest = ""; major_preference = ""; new_ec_name = ""
        saved_msg = ""
    f = _Fake()
    ProfileState.set_career_interest.fn(f, "x" * 5000)
    ProfileState.set_major_preference.fn(f, "y" * 5000)
    ProfileState.set_new_ec_name.fn(f, "z" * 5000)
    assert len(f.career_interest) == MAX_FIELD
    assert len(f.major_preference) == MAX_FIELD
    assert len(f.new_ec_name) == MAX_FIELD


def test_a_malformed_deadline_is_rejected_not_stored():
    from veritagnosis.states.profile_state import ProfileState

    class _Fake:
        app_deadline = "2026-01-15"; saved_msg = ""
    f = _Fake()
    ProfileState.set_app_deadline.fn(f, "not-a-date")
    assert f.app_deadline == "2026-01-15", "garbage overwrote a valid date"
    ProfileState.set_app_deadline.fn(f, "2026-11-01")
    assert f.app_deadline == "2026-11-01"


def test_the_backend_restricts_cors_origins():
    """Reflex defaults to '*', which would let any page on the internet open a
    websocket to this backend."""
    import reflex as rx
    origins = list(rx.config.get_config().cors_allowed_origins)
    assert origins, "no CORS origins configured"
    assert "*" not in origins, "backend accepts websockets from any origin"


def test_security_headers_are_attached():
    from veritagnosis.security import HEADERS
    assert HEADERS["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in HEADERS["content-security-policy"]
    assert "object-src 'none'" in HEADERS["content-security-policy"]
    assert HEADERS["x-content-type-options"] == "nosniff"


# ------------------------------ encrypting a column that shipped in the clear
def _raw_profile(uid):
    from sqlalchemy import text
    from veritagnosis import db as _db
    with _db.engine.begin() as c:
        return c.execute(text("SELECT profile_data FROM user WHERE id=:i"),
                         {"i": uid}).scalar()


def _write_raw_profile(uid, value):
    from sqlalchemy import text
    from veritagnosis import db as _db
    with _db.engine.begin() as c:
        c.execute(text("UPDATE user SET profile_data=:v WHERE id=:i"),
                  {"v": value, "i": uid})


def _new_user(prefix):
    import uuid
    from veritagnosis import db as _db
    from veritagnosis.models import User as _User
    with _db.get_session() as s:
        u = _User(username=f"{prefix}_{uuid.uuid4().hex[:8]}", password_hash="x")
        s.add(u); s.commit(); s.refresh(u)
        return u.id


def test_a_profile_row_written_before_encryption_still_reads():
    """profile_data shipped unencrypted and was encrypted afterwards. Any
    database created in between holds plaintext JSON there, and feeding that to
    the decryptor raises DecryptionError — which is the bug that took the
    profile screen down."""
    import json
    from veritagnosis import db as _db
    from veritagnosis.models import User as _User

    uid = _new_user("legacyread")
    legacy = '{"career_interest": "Computer Science", "priority": "balanced"}'
    _write_raw_profile(uid, legacy)

    with _db.get_session() as s:
        got = s.get(_User, uid).profile_data
    assert json.loads(got)["career_interest"] == "Computer Science"


def test_a_tampered_profile_row_still_fails_loudly():
    """The legacy tolerance must not become a blanket 'ignore decryption
    errors'. A value carrying the ciphertext envelope but failing its
    authentication tag is a wrong key or tampering, and must still raise."""
    import base64
    import pytest as _pytest
    from veritagnosis import db as _db
    from veritagnosis.models import User as _User
    from veritagnosis.crypto import DecryptionError, VERSION

    uid = _new_user("tampered")
    forged = base64.urlsafe_b64encode(VERSION + b"\x00" * 12 + b"garbage").decode()
    _write_raw_profile(uid, forged)

    with _pytest.raises(DecryptionError):
        with _db.get_session() as s:
            _ = s.get(_User, uid).profile_data


def test_other_encrypted_columns_did_not_get_the_tolerance():
    """Columns encrypted from the start have no legacy rows, so an unreadable
    value there is a real problem and must not be passed through as plaintext."""
    from veritagnosis.models import User as _User
    cols = _User.__table__.columns
    assert cols["profile_data"].type.legacy_plaintext is True
    for name in ("gpa", "age", "gender", "email"):
        assert cols[name].type.legacy_plaintext is False, \
            f"{name} must stay strict"


def test_the_migration_encrypts_legacy_rows_and_is_repeatable():
    import importlib.util
    from pathlib import Path
    from veritagnosis.crypto import looks_encrypted

    uid = _new_user("migrate")
    _write_raw_profile(uid, '{"career_interest": "Medicine"}')
    assert not looks_encrypted(_raw_profile(uid))

    spec = importlib.util.spec_from_file_location(
        "_manage", Path(__file__).resolve().parents[1] / "scripts" / "manage.py")
    manage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manage)

    assert manage.encrypt_profiles() == 0
    after = _raw_profile(uid)
    assert looks_encrypted(after)
    assert "Medicine" not in after

    # Running it twice must not double-encrypt.
    assert manage.encrypt_profiles() == 0
    assert _raw_profile(uid) == after


def test_the_profile_screen_survives_an_unreadable_profile():
    """One bad row must not take the whole screen down — the decrypt happens
    inside the ORM read, which was previously unguarded."""
    import asyncio
    import base64
    from veritagnosis.crypto import VERSION
    from veritagnosis.states.profile_state import ProfileState

    uid = _new_user("screendown")
    _write_raw_profile(
        uid, base64.urlsafe_b64encode(VERSION + b"\x00" * 12 + b"xx").decode())

    class _Fake:
        career_interest = ""; major_preference = ""; app_deadline = ""
        target_schools_count = 5; priority = "balanced"; extracurriculars = []
        loading = True; load_error = ""; form_epoch = 0
        readiness_overall = 0; readiness_dims = []; blind_spots = []
        next_steps = []; fits = []; disagreements = []; fit_warnings = []
        coverage_note = ""; school_count = 0; analysed = False
        async def _user_id(self): return uid
        def _analyse(self, _uid): pass

    f = _Fake()
    # asyncio.run, not get_event_loop: the latter is deprecated, and it
    # depends on global loop state that any earlier test using asyncio.run
    # will have torn down — which made this test pass or fail depending on
    # what ran before it.
    asyncio.run(ProfileState.load.fn(f))
    assert f.load_error, "an unreadable profile produced no explanation"
    assert f.career_interest == ""


# ====================================================================
# from test_encoding.py
# ====================================================================

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Only our own code. Anything vendored is not ours to fix.
OURS = [p for p in ROOT.rglob("*.py")
        if not any(part in {".venv", "venv", ".web", "__pycache__", "node_modules"}
                   for part in p.parts)]


def test_env_template_is_ascii():
    """The .env file is machine-parsed, so it must not contain a character that
    could be written as a non-UTF-8 byte."""
    src = (ROOT / "scripts" / "manage.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    template = next(
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and any(getattr(t, "id", "") == "TEMPLATE" for t in node.targets)
    )
    offenders = {c for c in template if not c.isascii()}
    assert not offenders, f".env template contains non-ASCII: {offenders}"


@pytest.mark.parametrize("path", OURS, ids=lambda p: str(p.relative_to(ROOT)))
def test_file_io_declares_an_encoding(path):
    """Every open()/write_text()/read_text() on a text file names its encoding.

    Binary modes are exempt: bytes have no encoding.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = getattr(fn, "id", None) or getattr(fn, "attr", None)

        if name == "open":
            mode = ""
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value or ""
            mode += "".join(
                k.value.value for k in node.keywords
                if k.arg == "mode" and isinstance(k.value, ast.Constant)
            )
            if "b" in mode:
                continue
            if not any(k.arg == "encoding" for k in node.keywords):
                problems.append(f"line {node.lineno}: open() without encoding=")

        elif name in {"write_text", "read_text"}:
            if not any(k.arg == "encoding" for k in node.keywords):
                problems.append(f"line {node.lineno}: {name}() without encoding=")

    assert not problems, f"{path.relative_to(ROOT)}:\n  " + "\n  ".join(problems)


# ====================================================================
# from test_schema_repair.py
# ====================================================================

@pytest.fixture
def stale_db(tmp_path, monkeypatch):
    """A database written by an older version of the app: the user table is
    missing `last_active`, and the newer feature tables do not exist at all."""
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE user (id INTEGER PRIMARY KEY, username VARCHAR NOT NULL,
          email VARCHAR, email_bidx VARCHAR, password_hash VARCHAR NOT NULL,
          age VARCHAR, gender VARCHAR, gpa VARCHAR, theme VARCHAR, avatar VARCHAR,
          xp INTEGER, streak_days INTEGER, is_active BOOLEAN, email_verified BOOLEAN,
          created_at DATETIME, failed_logins INTEGER, locked_until DATETIME);
        CREATE UNIQUE INDEX ix_user_username ON user (username);
        CREATE TABLE school (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
          name VARCHAR NOT NULL, tier VARCHAR, status VARCHAR, deadline DATETIME,
          progress INTEGER, notes VARCHAR);
    """)
    con.commit(); con.close()

    from veritagnosis import db, models  # noqa: F401
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(db, "engine", engine)
    return path, engine


def _columns(engine, table) -> set[str]:
    from sqlalchemy import inspect
    return {c["name"] for c in inspect(engine).get_columns(table)}


def test_missing_column_is_added(stale_db):
    from veritagnosis import db
    path, engine = stale_db
    assert "last_active" not in _columns(engine, "user"), "fixture is wrong"

    SQLModel.metadata.create_all(engine)
    added = db.ensure_schema(engine)

    assert "user.last_active" in added
    assert "last_active" in _columns(engine, "user")


def test_missing_tables_are_created(stale_db):
    from veritagnosis import db
    from sqlalchemy import inspect
    path, engine = stale_db

    SQLModel.metadata.create_all(engine)
    db.ensure_schema(engine)

    tables = set(inspect(engine).get_table_names())
    for expected in ("essay", "recommender", "meditationlog", "checkpointprogress"):
        assert expected in tables, f"{expected} was not created"


def test_signup_and_login_work_after_repair(stale_db):
    """The actual symptom: both were dead before the repair."""
    from veritagnosis import db
    from veritagnosis import security as auth
    path, engine = stale_db

    SQLModel.metadata.create_all(engine)
    db.ensure_schema(engine)

    with Session(engine) as s:
        user = auth.register(s, "sri", "correct-horse-42", email="a@b.com", age="17")
        assert user.id is not None
        # Two-factor is required, so sign in the way the app does: password
        # first, then the code. This also proves the repaired schema carries
        # the login_challenge table.
        try:
            auth.login(s, "sri", "correct-horse-42")
            raise AssertionError("login() must not return a session on its own")
        except auth.SecondFactorRequired as e:
            token, _ = auth.complete_login(s, e.challenge, e.code)
        assert auth.session_user(s, token).username == "sri"


def test_existing_rows_survive_the_repair(stale_db):
    """Repairing must not lose anyone's account."""
    from veritagnosis import db
    from veritagnosis.models import User
    path, engine = stale_db

    con = sqlite3.connect(path)
    con.execute("INSERT INTO user (username, password_hash, xp, theme) "
                "VALUES ('olduser', 'x', 250, 'cafe')")
    con.commit(); con.close()

    SQLModel.metadata.create_all(engine)
    db.ensure_schema(engine)

    with Session(engine) as s:
        row = s.exec(select(User).where(User.username == "olduser")).first()
        assert row is not None, "the existing account was lost"
        assert row.xp == 250 and row.theme == "cafe", "existing values changed"


def test_repair_is_idempotent(stale_db):
    from veritagnosis import db
    path, engine = stale_db
    SQLModel.metadata.create_all(engine)
    db.ensure_schema(engine)
    assert db.ensure_schema(engine) == [], "second run should change nothing"


# ====================================================================
# from test_state_isolation.py
# ====================================================================

SCREENS = [AchievementsState, AidState, AvatarState, EssayState,
           GrazeState, MeditationState, ProfileState, RecsState, SchoolsState]


# ------------------------------------------------------- 1. the stamp is per-screen
def test_feature_state_is_a_mixin_not_a_parent_state():
    """If this ever stops being a mixin, every screen goes back to sharing one
    stamp and the wipe silently stops happening."""
    assert getattr(FeatureState, "_mixin", False) is True, (
        "FeatureState must be declared with mixin=True; as a plain base class "
        "its fields are shared across every screen state")


@pytest.mark.parametrize("cls", SCREENS, ids=lambda c: c.__name__)
def test_each_screen_owns_its_stamp(cls):
    fields = cls.get_fields()
    assert "owner_id" in fields, f"{cls.__name__} has no ownership stamp"
    assert "loading" in fields
    assert "error" in fields


@pytest.mark.parametrize("cls", SCREENS, ids=lambda c: c.__name__)
def test_screens_are_siblings_not_nested(cls):
    """No screen may be another screen's parent — that is what would put their
    fields in the same place."""
    parent = cls.get_parent_state()
    assert parent not in SCREENS, (
        f"{cls.__name__} is a substate of {parent.__name__}; they would share "
        f"fields")


@pytest.mark.parametrize("cls", SCREENS, ids=lambda c: c.__name__)
def test_the_stamp_is_not_inherited_from_a_parent_state(cls):
    """The precise check for the bug this file exists to prevent.

    Reflex records, per state, which vars live on an ancestor rather than on
    the state itself. If `owner_id` ever shows up in `inherited_vars`, the five
    screens are reading and writing one shared value again and the ownership
    check has quietly stopped doing anything.
    """
    assert "owner_id" not in cls.inherited_vars, (
        f"{cls.__name__}.owner_id is inherited, so it is shared with the other "
        f"screens; FeatureState must be a mixin")
    assert "owner_id" in cls.vars


# --------------------------------------------------- 2. sign-out clears everything
def test_sign_out_clears_every_screen_state():
    """The sign-out handler must name every screen. A screen added later and
    forgotten here would keep its data across the switch, so this reads the
    source and checks the list is complete."""
    import inspect

    # .fn: Reflex wraps handlers in an EventHandler object
    src = inspect.getsource(AuthState.sign_out.fn)
    for cls in SCREENS:
        assert cls.__name__ in src, (
            f"{cls.__name__} is not cleared on sign out — a new screen was "
            f"added without updating AuthState.sign_out")


def test_auth_state_clears_its_own_display_fields():
    import inspect
    src = inspect.getsource(AuthState._clear_profile)
    for field in ("username", "display_name", "xp", "level", "avatar_json",
                  "streak", "essays_left", "schools_count", "owner_id"):
        assert field in src, f"_clear_profile leaves {field} behind"


# ------------------------------------------------------ 3. sessions cannot cross
@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _verified(db, username, password="Str0ng-Pass!42"):
    return auth.register(db, username, password,
                         email=f"{username}@example.com")


def _both_factors(db, username, password="Str0ng-Pass!42"):
    """Sign in properly. Returns (token, user)."""
    try:
        auth.login(db, username, password)
    except auth.SecondFactorRequired as e:
        return auth.complete_login(db, e.challenge, e.code)
    raise AssertionError("login() returned a session without a second factor")


def test_two_tokens_never_resolve_to_each_other(db_session):
    _verified(db_session, "amara")
    _verified(db_session, "boris")
    tok_a, ua = _both_factors(db_session, "amara")
    tok_b, ub = _both_factors(db_session, "boris")

    assert tok_a != tok_b
    assert auth.session_user(db_session, tok_a).id == ua.id
    assert auth.session_user(db_session, tok_b).id == ub.id


def test_a_signed_out_token_stops_resolving(db_session):
    _verified(db_session, "amara")
    tok, _ = _both_factors(db_session, "amara")
    assert auth.session_user(db_session, tok) is not None

    auth.logout(db_session, tok)
    assert auth.session_user(db_session, tok) is None, (
        "a revoked token must stop working immediately — this is what makes "
        "the ownership check resolve to None and wipe the screen")


def test_signing_in_as_someone_else_yields_a_different_user_id(db_session):
    """The exact sequence behind the bug: sign out, sign in as someone else on
    the same browser. The id the screens check against must change."""
    _verified(db_session, "amara")
    _verified(db_session, "boris")

    tok_a, ua = _both_factors(db_session, "amara")
    first = auth.session_user(db_session, tok_a).id
    auth.logout(db_session, tok_a)

    tok_b, ub = _both_factors(db_session, "boris")
    second = auth.session_user(db_session, tok_b).id

    assert first != second
    assert auth.session_user(db_session, tok_a) is None


# ====================================================================
# Structure — the failure modes that merging modules introduces
# ====================================================================
#
# These caught real bugs. When several modules were merged into one file, two
# things went wrong that neither the type checker nor the rest of the suite
# noticed, because both produce working-looking code that silently does the
# wrong thing:
#
#   * two sections each defined `_tile`, and the second quietly replaced the
#     first, so the avatar screen started calling the home screen's helper;
#   * two sections each imported a *different* module as `content`, and the
#     Graze screen started reading the checkpoint content instead of its own.
#
# Neither raised anything at import. Only rendering a page did.

def _project_modules():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    for p in sorted((root / "veritagnosis").rglob("*.py")):
        if "__pycache__" not in p.parts:
            yield p


def test_no_module_defines_the_same_name_twice():
    """A second `def foo` silently replaces the first. Python allows it and
    says nothing, and the loser is simply gone."""
    import ast
    from collections import Counter

    problems = []
    for p in _project_modules():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        names = [n.name for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef))]
        for name, count in Counter(names).items():
            if count > 1:
                problems.append(f"{p.name}: '{name}' defined {count}x")
    assert not problems, "shadowed definitions:\n  " + "\n  ".join(problems)


def test_no_module_binds_one_name_to_two_different_modules():
    """`import a as content` followed by `import b as content` leaves every
    `content.X` in the file pointing at whichever came last."""
    import ast
    from collections import defaultdict

    problems = []
    for p in _project_modules():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        bound = defaultdict(set)
        for n in tree.body:
            if isinstance(n, ast.ImportFrom):
                for a in n.names:
                    bound[a.asname or a.name].add(f"{n.module}.{a.name}")
            elif isinstance(n, ast.Import):
                for a in n.names:
                    bound[a.asname or a.name.split(".")[0]].add(a.name)
        for name, sources in bound.items():
            if len(sources) > 1:
                problems.append(f"{p.name}: '{name}' -> {sorted(sources)}")
    assert not problems, "conflicting import aliases:\n  " + "\n  ".join(problems)


def test_every_page_actually_renders():
    """The import graph can be perfectly healthy while a page still explodes
    on render — a shadowed helper with a different signature, a Var used where
    a value is needed. Importing the module is not enough; the component tree
    has to be built."""
    import veritagnosis.veritagnosis  # noqa: F401  (registers everything)
    from veritagnosis.pages import aid, apply, auth, home, play, profile

    pages = [
        ("splash", auth.splash), ("login", auth.login), ("signup", auth.signup),
        ("verify", auth.verify), ("settings", auth.settings_page),
        ("home", home.home), ("achievements", home.achievements_page),
        ("avatar", home.avatar_page),
        ("applications", apply.applications_page),
        ("essays", apply.essays_page),
        ("recommendations", apply.recommendations_page),
        ("meditation", play.meditation_page), ("graze", play.graze_page),
        ("profile", profile.profile_page), ("aid", aid.aid_page),
    ]
    for name, fn in pages:
        try:
            assert str(fn().render()), f"{name} rendered empty"
        except Exception as exc:                       # noqa: BLE001
            raise AssertionError(f"page '{name}' failed to render: {exc}") from exc
