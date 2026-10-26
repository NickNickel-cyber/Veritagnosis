
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

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    code_hash: str
    expires_at: datetime = Field(sa_column=Column(UTCDateTime, nullable=False))
    attempts: int = Field(default=0)
    used: bool = Field(default=False)


class LoginChallenge(SQLModel, table=True):

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



class College(SQLModel, table=True):

    id: int | None = Field(default=None, primary_key=True)

    # The Scorecard's stable institution id. Unique, so a re-import updates
    # rows in place rather than doubling the table.
    unitid: int = Field(index=True, unique=True)

    name: str = Field(index=True, max_length=200)
    # Lowercased name, for case-insensitive matching without a function index
    # (SQLite will not use an index for lower(name)).
    name_key: str = Field(index=True, max_length=200)
    state: str = Field(default="", max_length=2, index=True)
    city: str = Field(default="", max_length=120)
    control: str = Field(default="", max_length=20)   # public | private | for-profit

    accept_rate: float | None = None      # percent, 0-100, to match the curated set
    sat_25: int | None = None
    sat_75: int | None = None
    act_25: int | None = None
    act_75: int | None = None

    cost_year: int | None = None          # average total annual cost
    tuition_in: int | None = None
    tuition_out: int | None = None
    net_price: int | None = None          # average net price after aid
    size: int | None = None               # undergraduate enrolment

    data_year: str = Field(default="", max_length=16)
    source_url: str = Field(default="", max_length=300)
    source_kind: str = Field(default="college_scorecard", max_length=40)
    confidence: str = Field(default="medium", max_length=10)
    test_optional_note: str | None = Field(default=None, max_length=300)

    def as_dict(self) -> dict:
        """The same shape content/colleges.py uses, so callers need no branch."""
        return {
            "name": self.name, "state": self.state, "city": self.city,
            "control": self.control,
            "accept_rate": self.accept_rate,
            "sat_25": self.sat_25, "sat_75": self.sat_75,
            "act_25": self.act_25, "act_75": self.act_75,
            "gpa_375_plus_pct": None,     # the Scorecard does not publish this
            "cost_year": self.cost_year,
            "tuition_in": self.tuition_in, "tuition_out": self.tuition_out,
            "net_price": self.net_price, "size": self.size,
            "data_year": self.data_year, "source_url": self.source_url,
            "source_kind": self.source_kind, "confidence": self.confidence,
            "test_optional_note": self.test_optional_note,
            "note": "",
        }


class School(SQLModel, table=True):
    """One college on the list. The wireframe groups these into Safety / Reach
    columns, which is what `tier` drives."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(max_length=120)
    tier: Tier = Field(default=Tier.target)
    status: AppStatus = Field(default=AppStatus.not_started)
    deadline: datetime | None = Field(default=None, sa_column=Column(UTCDateTime))

    progress: int = Field(default=0)
    notes: str | None = Field(default=None, sa_column=Column(Encrypted("school.notes")))

    essays_required: int = Field(default=1)
    recs_required: int = Field(default=2)
    submitted_at: datetime | None = Field(default=None, sa_column=Column(UTCDateTime))

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


class CheckpointProgress(SQLModel, table=True):

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    checkpoint_key: str = Field(max_length=40, index=True)
    reached_at: datetime = Field(default_factory=utcnow,
                                 sa_column=Column(UTCDateTime))


class EssayVersion(SQLModel, table=True):

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    essay_id: int = Field(foreign_key="essay.id", index=True)
    body: str | None = Field(default=None, sa_column=Column(Encrypted("version.body")))
    words: int = Field(default=0)
    score: int = Field(default=0)
    label: str = Field(default="", max_length=60)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(UTCDateTime))


class Scholarship(SQLModel, table=True):

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

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    task_key: str = Field(max_length=40, index=True)
    done_at: datetime = Field(default_factory=utcnow, sa_column=Column(UTCDateTime))


class CalmLog(SQLModel, table=True):

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    kind: str = Field(default="graze", max_length=16)     # graze | calm
    minutes: int = Field(default=0)
    score: int = Field(default=0)
    detail: str = Field(default="", max_length=60)
    finished_at: datetime = Field(default_factory=utcnow, sa_column=Column(UTCDateTime))
