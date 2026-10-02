"""
Database tables.

Which columns are encrypted, and why:

  encrypted   email, age, gender, gpa, test scores, school notes
              Either legally sensitive (a minor's age and gender) or
              embarrassing/competitively useful if a classmate read it.

  plaintext   username, school names, application status, deadlines
              Username has to be searchable and is semi-public anyway. School
              names and deadlines are low-harm and are queried and sorted
              constantly; encrypting them would mean decrypting every row to
              sort by deadline, for very little gain.

That line is a judgement call, and it is the one worth defending in a writeup:
encrypt what would hurt, keep queryable what has to be queried.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, TypeDecorator
from sqlmodel import Field, SQLModel

from veritagnosis.crypto import Encrypted


def utcnow() -> datetime:
    """Timezone-aware UTC. Naive datetimes in a database are a bug waiting to
    happen the first time the app runs in another timezone."""
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Always store UTC, always read back timezone-aware.

    SQLite has no datetime type — it stores a string and hands it back naive.
    Comparing that to an aware `utcnow()` raises TypeError, and the tempting fix
    (making everything naive) silently breaks the moment the app runs anywhere
    but UTC. Normalising at the column boundary means no comparison anywhere
    else has to think about it.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:                 # assume naive input is UTC
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _utc_col(**kw):
    return Field(sa_column=Column(UTCDateTime, **kw))


class Tier(str, Enum):
    safety = "safety"
    target = "target"
    reach = "reach"


class AppStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    submitted = "submitted"
    accepted = "accepted"
    rejected = "rejected"
    waitlisted = "waitlisted"


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    # Plaintext: needed for login lookup and uniqueness.
    username: str = Field(index=True, unique=True, max_length=32)

    # Encrypted, plus a blind index so login-by-email still works. See
    # crypto.blind_index for why this is safe here but not for age or gender.
    email: str | None = Field(default=None, sa_column=Column(Encrypted("user.email")))
    email_bidx: str | None = Field(default=None, index=True)

    password_hash: str  # Argon2id. Never a password, never reversible.

    # Minor's personal data — encrypted at rest.
    age: str | None = Field(default=None, sa_column=Column(Encrypted("user.age")))
    gender: str | None = Field(default=None, sa_column=Column(Encrypted("user.gender")))
    gpa: str | None = Field(default=None, sa_column=Column(Encrypted("user.gpa")))

    theme: str = Field(default="serenity", max_length=20)
    avatar: str = Field(default="{}", max_length=512)   # JSON blob of part indexes
    # Career, major, activities, deadline. Encrypted on the same rule as the
    # rest: it is never queried or sorted across users, and what a student is
    # into and how much of their life goes into it is exactly the sort of
    # thing that would sting if a classmate read it.
    # legacy_plaintext: this column shipped unencrypted and was encrypted
    # afterwards, so databases created in between hold plaintext JSON here.
    # Those rows are read as-is and re-encrypted on the next save.
    # `python scripts/manage.py encrypt-profiles` converts them all at once.
    profile_data: str | None = Field(
        default=None,
        sa_column=Column(Encrypted("user.profile", legacy_plaintext=True)))
    xp: int = Field(default=0)
    streak_days: int = Field(default=0)
    last_active: datetime | None = Field(default=None, sa_column=Column(UTCDateTime))

    is_active: bool = Field(default=True)
    email_verified: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(UTCDateTime))

    # Online-guessing defence. Counts reset on a successful login.
    failed_logins: int = Field(default=0)
    locked_until: datetime | None = Field(default=None, sa_column=Column(UTCDateTime))

    def is_locked(self) -> bool:
        return self.locked_until is not None and self.locked_until > utcnow()


class AuthSession(SQLModel, table=True):
    """A logged-in session.

    Only the SHA-256 of the token is stored, exactly like an API key: if the
    database leaks, the rows cannot be replayed as valid sessions. The raw token
    exists only in the user's cookie and briefly in memory at login.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token_hash: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(UTCDateTime))
    last_seen: datetime = Field(default_factory=utcnow, sa_column=Column(UTCDateTime))
    expires_at: datetime = Field(sa_column=Column(UTCDateTime, nullable=False))
    revoked: bool = Field(default=False)

    # Recorded so a student can see "signed in on a Windows PC, Tuesday" and
    # spot a session that is not theirs. Truncated deliberately — see security/auth.py.
    user_agent: str | None = Field(default=None, max_length=120)

    def is_valid(self, idle_hours: int) -> bool:
        now = utcnow()
        return (
            not self.revoked
            and self.expires_at > now
            and self.last_seen > now - timedelta(hours=idle_hours)
        )


class EmailToken(SQLModel, table=True):
    """Six-digit verification code from the wireframe.

    Hashed, single-use, short-lived, and attempt-capped — otherwise a six-digit
    code is a million guesses, which is nothing."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    code_hash: str
    expires_at: datetime = Field(sa_column=Column(UTCDateTime, nullable=False))
    attempts: int = Field(default=0)
    used: bool = Field(default=False)


class LoginChallenge(SQLModel, table=True):
    """A login that has passed the password and is waiting on the second factor.

    This exists so that a correct password is never, on its own, a session.
    Between the two steps the browser holds nothing but `handle` — 256 random
    bits that mean nothing anywhere else. Notably it does NOT hold the user id:
    the previous flow kept that in local storage, which told anyone reading the
    browser's storage exactly whose account was part-way through signing in,
    and let them point the verify step at any account they liked.

    The row is single-use and attempt-capped, because six digits is only a
    million guesses and an uncapped endpoint would exhaust that in an afternoon.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    # SHA-256 of the raw handle. Same reasoning as AuthSession.token_hash: a
    # leaked database must not yield replayable handles.
    handle_hash: str = Field(index=True, unique=True)

    # Keyed MAC, not a bare hash — see crypto.code_mac.
    code_hash: str

    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(UTCDateTime))
    expires_at: datetime = Field(sa_column=Column(UTCDateTime, nullable=False))
    attempts: int = Field(default=0)
    used: bool = Field(default=False)

    # Carried across the two steps so the session that is eventually created
    # records the device that actually asked for it.
    user_agent: str | None = Field(default=None, max_length=120)

    def is_live(self) -> bool:
        return (not self.used
                and self.expires_at > utcnow()
                and self.attempts < 5)


class School(SQLModel, table=True):
    """One college on the list. The wireframe groups these into Safety / Reach
    columns, which is what `tier` drives."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(max_length=120)
    tier: Tier = Field(default=Tier.target)
    status: AppStatus = Field(default=AppStatus.not_started)
    deadline: datetime | None = Field(default=None, sa_column=Column(UTCDateTime))

    # 0-100, drives the ring. NOT typed in by the student any more — it is
    # recomputed from the actual work (services/progress.py) every time the
    # screen loads. Kept as a column so the home screen and the achievements
    # can read a school's progress without re-running the whole calculation.
    progress: int = Field(default=0)
    notes: str | None = Field(default=None, sa_column=Column(Encrypted("school.notes")))

    # What this particular college asks for. Different schools want different
    # numbers of essays and letters, and the progress calculation has to know
    # which, or "recommenders done" means nothing.
    essays_required: int = Field(default=1)
    recs_required: int = Field(default=2)
    submitted_at: datetime | None = Field(default=None, sa_column=Column(UTCDateTime))

    # Which round. This is not cosmetic: Early Decision is binding, and a
    # student holding two ED applications has a real problem the app should
    # notice rather than a preference it should store quietly.
    round: str = Field(default="regular", max_length=12)   # ed | ed2 | ea | rea | regular | rolling

    # Money. Encrypted — what a family can afford is nobody else's business,
    # and a leaked spreadsheet of "gap: $34,000" is genuinely harmful.
    sticker: str | None = Field(default=None, sa_column=Column(Encrypted("school.sticker")))
    net_cost: str | None = Field(default=None, sa_column=Column(Encrypted("school.net")))
    aid_offered: str | None = Field(default=None, sa_column=Column(Encrypted("school.aid")))
    aid_deadline: datetime | None = Field(default=None, sa_column=Column(UTCDateTime))
    needs_css: bool = Field(default=False)


class TestScore(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    kind: str = Field(max_length=16)     # SAT, ACT, AP Bio, ...
    score: str | None = Field(default=None, sa_column=Column(Encrypted("score.score")))
    taken_on: datetime | None = Field(default=None, sa_column=Column(UTCDateTime))


class Essay(SQLModel, table=True):
    """A draft the student is writing, with the coach's position in it.

    `body` is encrypted: an application essay is the most personal thing this
    app holds. `step` is which piece of coaching they are on, so the guide
    picks up where they left off instead of starting over.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    school_id: int | None = Field(default=None, foreign_key="school.id")
    prompt: str = Field(default="", max_length=300)
    body: str | None = Field(default=None, sa_column=Column(Encrypted("essay.body")))
    word_target: int = Field(default=300)
    step: int = Field(default=0)
    done: bool = Field(default=False)
    # How the writer feels about the draft right now. Drives what the guide
    # says next, so the buttons beside the editor are not decoration.
    reaction: str = Field(default="", max_length=12)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(UTCDateTime))
    updated_at: datetime = Field(default_factory=utcnow, sa_column=Column(UTCDateTime))


class Recommender(SQLModel, table=True):
    """A teacher or counsellor being asked for a letter.

    Name and note are encrypted — who a student asked, and what they said about
    them, is gossip if it leaks.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str | None = Field(default=None, sa_column=Column(Encrypted("rec.name")))
    role: str = Field(default="teacher", max_length=16)   # teacher | guidance
    subject: str = Field(default="", max_length=60)
    status: str = Field(default="not_asked", max_length=16)
    note: str | None = Field(default=None, sa_column=Column(Encrypted("rec.note")))
    asked_on: datetime | None = Field(default=None, sa_column=Column(UTCDateTime))
    # When the student decided to chase this one up. Set by hand or suggested
    # by the screen; nothing is emailed, it only surfaces on the list.
    follow_up_on: datetime | None = Field(default=None, sa_column=Column(UTCDateTime))
    # The letter is due for these colleges. Stored as a comma-separated list of
    # school ids: a join table for at most a handful of ids per person would be
    # more machinery than the problem deserves.
    school_ids: str = Field(default="", max_length=200)


class MeditationLog(SQLModel, table=True):
    """One finished session. Drives the streak and the XP award."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    kind: str = Field(default="breathing", max_length=24)
    pattern: str = Field(default="box", max_length=16)
    minutes: int = Field(default=2)
    finished_at: datetime = Field(default_factory=utcnow, sa_column=Column(UTCDateTime))


class AuditLog(SQLModel, table=True):
    """Append-only record of security-relevant events. See security/auth.py."""

    id: int | None = Field(default=None, primary_key=True)
    at: datetime = Field(default_factory=utcnow, sa_column=Column(UTCDateTime, index=True))
    user_id: int | None = Field(default=None, index=True)
    action: str = Field(max_length=48)
    detail: str | None = Field(default=None, max_length=256)
    ok: bool = Field(default=True)



# ---------------------------------------------------------------------------
# Roadmap progress. The checkpoints themselves are content, not data --
# they live in content/meditation.py, the same for every student -- so only
# the *reaching* of one is stored here. The roadmap can be rewritten or
# reordered without a database migration.
# ---------------------------------------------------------------------------

class CheckpointProgress(SQLModel, table=True):
    """Which roadmap checkpoints a student has reached.

    The checkpoints themselves are content, not data — they live in
    content/meditation.py and are the same for everyone. Only the *reaching* of
    one is per-user, so only that is stored.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    checkpoint_key: str = Field(max_length=40, index=True)
    reached_at: datetime = Field(default_factory=utcnow,
                                 sa_column=Column(UTCDateTime))


class EssayVersion(SQLModel, table=True):
    """A saved snapshot of a draft.

    Undo covers the last change. This covers the other kind of regret: the one
    where you rewrote the whole middle section yesterday and now want the old
    version back. Students edit their personal statement thirty or forty times
    over three months, and without this there is no way back to a paragraph
    they deleted in week two.

    The body is encrypted exactly like the live draft, because a snapshot of a
    personal essay is every bit as personal as the essay.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    essay_id: int = Field(foreign_key="essay.id", index=True)
    body: str | None = Field(default=None, sa_column=Column(Encrypted("version.body")))
    words: int = Field(default=0)
    score: int = Field(default=0)
    label: str = Field(default="", max_length=60)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(UTCDateTime))


class Scholarship(SQLModel, table=True):
    """One scholarship the student is chasing.

    Separate from School because most scholarships are not attached to a
    college — they are local, corporate, or from a foundation, and they are the
    part of paying for college that students most often never get round to.
    A named list with deadlines is most of the battle.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(max_length=140)
    amount: str | None = Field(default=None, sa_column=Column(Encrypted("scholar.amount")))
    deadline: datetime | None = Field(default=None, sa_column=Column(UTCDateTime))
    status: str = Field(default="found", max_length=16)   # found|started|submitted|won|lost
    url: str = Field(default="", max_length=300)
    notes: str | None = Field(default=None, sa_column=Column(Encrypted("scholar.notes")))
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(UTCDateTime))


class AidTask(SQLModel, table=True):
    """A step in the financial aid paperwork, ticked off by the student.

    The steps themselves are content (content/aid.py), the same for everyone,
    so only the *doing* of one is stored — the same pattern as the meditation
    roadmap and the checkpoints.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    task_key: str = Field(max_length=40, index=True)
    done_at: datetime = Field(default_factory=utcnow, sa_column=Column(UTCDateTime))


class CalmLog(SQLModel, table=True):
    """One finished session on a stress screen — the game or the tap screen.

    Deliberately the same shape as MeditationLog rather than reusing it: these
    are a different kind of break, and mixing them would corrupt the meditation
    streak that several checkpoints depend on.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    kind: str = Field(default="graze", max_length=16)     # graze | calm
    minutes: int = Field(default=0)
    score: int = Field(default=0)
    detail: str = Field(default="", max_length=60)
    finished_at: datetime = Field(default_factory=utcnow, sa_column=Column(UTCDateTime))
