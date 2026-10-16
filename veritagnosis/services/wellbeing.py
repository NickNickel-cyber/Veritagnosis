"""
Checkpoints, meditation and breaks — the parts of the app that
are about the person rather than the application.

Merged from: achievements, meditation, breaks.
"""
from __future__ import annotations

import dataclasses
from sqlmodel import Session, select
from veritagnosis.content import achievements as content
from veritagnosis.models import (AidTask, AppStatus, CalmLog, CheckpointProgress,
                                 Essay, MeditationLog, Recommender, School,
                                 Scholarship, User, utcnow)
from veritagnosis.services import prose
from veritagnosis.models import MeditationLog, User
from veritagnosis.services import insight as profile
from veritagnosis.ui.widgets import PATTERNS
from veritagnosis.models import CalmLog, User, utcnow


# ====================================================================
# achievements
# ====================================================================

@dataclasses.dataclass
class Badge:
    """One achievement, ready for the screen."""

    key: str
    title: str
    blurb: str
    icon: str
    xp: int
    cat: str
    cat_name: str
    reached: bool
    percent: int


def gather(session: Session, user_id: int) -> dict:
    """Everything the achievement list can ask about, computed from real rows."""
    user = session.get(User, user_id)

    essays = list(session.exec(
        select(Essay).where(Essay.user_id == user_id)).all())
    words = 0
    best = 0
    polished = 0
    for e in essays:
        body = e.body or ""
        words += len(prose.words(body))
        s = prose.score(body)
        best = max(best, s)
        if s >= 70:
            polished += 1

    schools = list(session.exec(
        select(School).where(School.user_id == user_id)).all())
    sent_states = (AppStatus.submitted, AppStatus.accepted,
                   AppStatus.rejected, AppStatus.waitlisted)

    recs = list(session.exec(
        select(Recommender).where(Recommender.user_id == user_id)).all())

    logs = list(session.exec(
        select(MeditationLog).where(MeditationLog.user_id == user_id)).all())
    days = sorted({l.finished_at.date() for l in logs}, reverse=True)
    streak = 0
    if days and (utcnow().date() - days[0]).days <= 1:
        streak, cursor = 1, days[0]
        for d in days[1:]:
            if (cursor - d).days == 1:
                streak += 1
                cursor = d
            else:
                break

    aid_steps = list(session.exec(
        select(AidTask).where(AidTask.user_id == user_id)).all())
    scholarships = list(session.exec(
        select(Scholarship).where(Scholarship.user_id == user_id)).all())
    breaks_ = list(session.exec(
        select(CalmLog).where(CalmLog.user_id == user_id)).all())
    priced = sum(1 for s in schools
                 if (s.net_cost or s.sticker or s.aid_offered))

    xp = user.xp if user else 0
    return {
        "aid_steps": len(aid_steps),
        "scholarships": len(scholarships),
        "scholarships_sent": sum(1 for x in scholarships
                                 if x.status in ("submitted", "won")),
        "priced": priced,
        "break_sessions": len(breaks_),
        "break_minutes": sum(b.minutes for b in breaks_),
        "essays": len(essays),
        "essay_words": words,
        "essay_best": best,
        "essay_polished": polished,
        "essay_finished": sum(1 for e in essays if e.done),

        "schools": len(schools),
        "schools_started": sum(1 for s in schools if s.progress > 5),
        "schools_ready": sum(1 for s in schools if s.progress >= 80),
        "schools_submitted": sum(1 for s in schools if s.status in sent_states),
        "deadlines": sum(1 for s in schools if s.deadline is not None),

        "recs_asked": sum(1 for r in recs
                          if r.status in ("asked", "agreed", "submitted")),
        "recs_agreed": sum(1 for r in recs if r.status in ("agreed", "submitted")),
        "recs_submitted": sum(1 for r in recs if r.status == "submitted"),

        "med_sessions": len(logs),
        "med_minutes": sum(l.minutes for l in logs),
        "med_streak": streak,

        "avatar": 1 if (user and user.avatar and user.avatar not in ("{}", "")) else 0,
        "level": 1 + xp // 500,
        "xp": xp,
    }


def reached_keys(session: Session, user_id: int) -> set[str]:
    return {r.checkpoint_key for r in session.exec(
        select(CheckpointProgress)
        .where(CheckpointProgress.user_id == user_id)).all()
        if r.checkpoint_key.startswith("a_")}


def award(session: Session, user_id: int, stats: dict | None = None) -> list[dict]:
    """Write down anything newly earned and pay out its XP.

    Returns the achievements that are new *this call*, so the screen can
    celebrate them. Safe to call as often as you like: anything already
    recorded is skipped, so no XP is ever paid twice.
    """
    if stats is None:
        stats = gather(session, user_id)

    already = reached_keys(session, user_id)
    newly: list[dict] = []
    user = session.get(User, user_id)

    for key in content.unlocked(stats):
        if key in already:
            continue
        session.add(CheckpointProgress(user_id=user_id, checkpoint_key=key))
        a = content.BY_KEY[key]
        newly.append(a)
        if user:
            user.xp += a["xp"]

    if newly and user:
        session.add(user)
    if newly:
        session.commit()
    return newly


def board(session: Session, user_id: int, stats: dict | None = None) -> list[Badge]:
    """The whole list, in display order, with progress on the unreached ones."""
    if stats is None:
        stats = gather(session, user_id)
    reached = reached_keys(session, user_id)
    names = dict(content.CATEGORIES)
    order = {k: i for i, (k, _) in enumerate(content.CATEGORIES)}

    badges = [
        Badge(key=a["key"], title=a["title"], blurb=a["blurb"], icon=a["icon"],
              xp=a["xp"], cat=a["cat"], cat_name=names.get(a["cat"], a["cat"]),
              reached=a["key"] in reached,
              percent=100 if a["key"] in reached else content.progress_to(a, stats))
        for a in content.ACHIEVEMENTS
    ]
    # Category order, then earned ones first inside each category so the board
    # reads as a record of what you have done rather than a list of what you
    # have not.
    badges.sort(key=lambda b: (order.get(b.cat, 99), not b.reached, -b.percent))
    return badges


def totals(session: Session, user_id: int) -> dict:
    reached = reached_keys(session, user_id)
    earned = [content.BY_KEY[k] for k in reached if k in content.BY_KEY]
    return {
        "reached": len(earned),
        "total": len(content.ACHIEVEMENTS),
        "xp": sum(a["xp"] for a in earned),
        "xp_total": content.TOTAL_XP,
        "percent": int(round(100 * len(earned) / len(content.ACHIEVEMENTS)))
                   if content.ACHIEVEMENTS else 0,
    }


# ====================================================================
# meditation
# ====================================================================

OPTIONS = [
    {"key": "calm", "title": "Calm meditation",
     "blurb": "A guided breathing exercise. Pick a pattern and a length.",
     "icon": "\U0001FAB7"},
    {"key": "types", "title": "Types of meditation",
     "blurb": "What the different kinds are for, and which suits the mood you're in.",
     "icon": "\U0001F9ED"},
    {"key": "reading", "title": "Meditation reading",
     "blurb": "Short pieces to read when you don't want to close your eyes.",
     "icon": "\U0001F4D6"},
]

# Content for "Types of meditation" — plain, non-mystical, aimed at a teenager
# who is stressed rather than seeking a practice.
TYPES = [
    ("Breath focus", "Count the breath and nothing else. The one to use when your "
                     "head is racing before a deadline."),
    ("Body scan", ("Move your attention slowly from your feet to your head. Good for "
                   "when you can't sleep.")),
    ("Walking", ("Walk slowly outside with your eyes open and pay attention to each "
                 "step. Good when sitting still makes it worse.")),
    ("Loving-kindness", "Wish someone well on purpose, including yourself. Helps "
                        "after a rejection or a bad comparison spiral."),
]

READINGS = [
    ("You are not behind",
     ("Application timelines are made up. Every deadline is just a date "
      "somebody picked, and it says nothing about you. Tonight, pick one "
      "thing you can move forward before bed.")),
    ("On comparing lists",
     ("Someone in your grade has a longer list, a higher score, or a better "
      "story. They're also stressed tonight. Their path isn't yours, so try "
      "not to grade yourself against it.")),
    ("The draft is allowed to be bad",
     ("A first draft is supposed to be messy. You can't edit a blank page, "
      "and nobody is grading the version no one will read.")),
]


def log_session(session: Session, user: User, pattern: str, minutes: int) -> int:
    """Record a finished session and pay out. Returns XP awarded."""
    session.add(MeditationLog(user_id=user.id, pattern=pattern, minutes=minutes))
    session.commit()
    xp = 10 + minutes * 5
    profile.award_xp(session, user, xp)
    profile.touch_streak(session, user)
    return xp


def total_minutes(session: Session, user_id: int) -> int:
    rows = session.exec(
        select(MeditationLog).where(MeditationLog.user_id == user_id)).all()
    return sum(r.minutes for r in rows)


def session_count(session: Session, user_id: int) -> int:
    return len(session.exec(
        select(MeditationLog).where(MeditationLog.user_id == user_id)).all())


def patterns() -> list[dict]:
    return PATTERNS


# ====================================================================
# breaks
# ====================================================================

XP_PER_MINUTE = 6
XP_CAP = 150


def log(session: Session, user_id: int, kind: str, minutes: int,
        score: int = 0, detail: str = "") -> int:
    """Record a finished session and pay the XP. Returns the XP awarded."""
    minutes = max(0, min(60, int(minutes or 0)))
    if minutes <= 0:
        return 0

    session.add(CalmLog(user_id=user_id, kind=kind[:16], minutes=minutes,
                        score=max(0, int(score or 0)), detail=detail[:60],
                        finished_at=utcnow()))
    gained = min(XP_CAP, minutes * XP_PER_MINUTE)
    user = session.get(User, user_id)
    if user:
        user.xp += gained
        session.add(user)
    session.commit()
    return gained


def stats(session: Session, user_id: int, kind: str | None = None) -> dict:
    q = select(CalmLog).where(CalmLog.user_id == user_id)
    if kind:
        q = q.where(CalmLog.kind == kind)
    rows = list(session.exec(q).all())
    return {
        "sessions": len(rows),
        "minutes": sum(r.minutes for r in rows),
        "best": max((r.score for r in rows), default=0),
        "last": max((r.finished_at for r in rows), default=None),
    }
