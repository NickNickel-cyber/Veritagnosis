"""
The application itself: progress across schools, the school list,
essays, and recommenders.

Merged from: progress, schools, essays, recommenders.
"""
from __future__ import annotations

import dataclasses
from datetime import timedelta
from sqlmodel import Session, select
from veritagnosis.models import (AppStatus, Essay, Recommender, School,
                                 TestScore, utcnow)
from veritagnosis.services import prose
from datetime import datetime
from veritagnosis.models import AppStatus, School, Tier, User
from veritagnosis.services import insight as profile
from veritagnosis.models import Essay, User, utcnow
from veritagnosis.models import Recommender, User, utcnow


# ====================================================================
# progress
# ====================================================================

@dataclasses.dataclass
class Milestone:
    """One thing that has to happen for an application to be finished."""

    key: str
    label: str          # what it is, in the student's words
    done: bool
    weight: int         # how much of the 100 it is worth
    hint: str           # what to do about it, if it is not done
    route: str          # which screen does it
    detail: str = ""    # progress within this milestone, e.g. "1 of 2 letters"


# How much each part of an application is worth. Essays are the largest share
# because they are the largest amount of work and the part students put off
# longest; the small ones are quick wins that make the ring move early.
WEIGHTS = {
    "listed": 5,
    "deadline": 10,
    "why": 10,
    "draft": 25,
    "polish": 15,
    "recs": 20,
    "scores": 10,
    "submit": 5,
}

# A draft counts as "drafted" at this fraction of the word target. Not 100%:
# a 650-word essay at 400 words is genuinely a draft, and telling someone they
# have made no progress until the last word is both wrong and demoralising.
DRAFT_FRACTION = 0.6

# The essay score at which a draft stops being a draft.
POLISH_SCORE = 70


def _school_essays(session: Session, user_id: int, school_id: int) -> list[Essay]:
    return list(session.exec(
        select(Essay).where(Essay.user_id == user_id,
                            Essay.school_id == school_id)).all())


def milestones(session: Session, user_id: int, school: School) -> list[Milestone]:
    """Everything this application still needs, and what is already done."""
    essays = _school_essays(session, user_id, school.id)

    # The general essay counts toward every school that has no essay of its own
    # — one personal statement really does go to all of them.
    if not essays:
        essays = list(session.exec(
            select(Essay).where(Essay.user_id == user_id,
                                Essay.school_id == None)).all())  # noqa: E711

    best_words = 0
    best_score = 0
    for e in essays:
        target = e.word_target or 650
        words = len(prose.words(e.body or ""))
        best_words = max(best_words, int(100 * words / target) if target else 0)
        best_score = max(best_score, prose.score(e.body or ""))

    recs = list(session.exec(
        select(Recommender).where(Recommender.user_id == user_id)).all())
    secured = sum(1 for r in recs if r.status in ("agreed", "submitted"))

    scores = list(session.exec(
        select(TestScore).where(TestScore.user_id == user_id)).all())

    notes = (school.notes or "").strip()
    need_recs = max(0, school.recs_required or 0)

    return [
        Milestone("listed", "On your list", True, WEIGHTS["listed"],
                  "", "/applications"),

        Milestone("deadline", "Deadline set", school.deadline is not None,
                  WEIGHTS["deadline"],
                  "Add the deadline so this can warn you before it arrives.",
                  "/applications"),

        Milestone("why", "Why this college", len(notes) >= 80, WEIGHTS["why"],
                  "Write a few lines on why you actually want to go here. "
                  "You will need them later, and it is much easier now.",
                  "/applications",
                  f"{len(notes)} characters" if notes else ""),

        Milestone("draft", "Essay drafted", best_words >= DRAFT_FRACTION * 100,
                  WEIGHTS["draft"],
                  "Get a draft down. It does not have to be good yet.",
                  "/essays",
                  f"{min(100, best_words)}% of the word target"),

        Milestone("polish", "Essay polished", best_score >= POLISH_SCORE,
                  WEIGHTS["polish"],
                  f"The coach scores your draft {best_score}. Clear the red "
                  f"items to get it past {POLISH_SCORE}.",
                  "/essays",
                  f"scores {best_score}" if best_score else ""),

        Milestone("recs", "Letters secured",
                  need_recs == 0 or secured >= need_recs, WEIGHTS["recs"],
                  "Ask your teachers. The earlier you ask, the better the "
                  "letter — they are writing dozens of these in December.",
                  "/recommendations",
                  f"{secured} of {need_recs} agreed" if need_recs else "none needed"),

        Milestone("scores", "Test scores recorded", bool(scores),
                  WEIGHTS["scores"],
                  "Record your SAT, ACT or AP results so you are not digging "
                  "them out the night before.",
                  "/settings"),

        Milestone("submit", "Submitted",
                  school.status in (AppStatus.submitted, AppStatus.accepted,
                                    AppStatus.rejected, AppStatus.waitlisted),
                  WEIGHTS["submit"],
                  "Mark it submitted once it is actually sent.",
                  "/applications"),
    ]


def percent(ms: list[Milestone]) -> int:
    """The ring. Weighted, so finishing the essay moves it more than adding a
    deadline — because it is more work and it matters more."""
    total = sum(m.weight for m in ms) or 1
    return int(round(100 * sum(m.weight for m in ms if m.done) / total))


def next_step(ms: list[Milestone]) -> Milestone | None:
    """The single most valuable unfinished thing.

    Heaviest first, so the answer to "what should I do about Michigan" is the
    thing that actually moves the needle, not whichever box happens to be
    nearest the top.
    """
    todo = [m for m in ms if not m.done and m.hint]
    return max(todo, key=lambda m: m.weight) if todo else None


def recompute(session: Session, user_id: int, school: School) -> int:
    """Work out the percentage and write it back. Returns it."""
    ms = milestones(session, user_id, school)
    pct = percent(ms)
    school.progress = pct

    # Status follows the work rather than being set by hand — except once
    # something is submitted or decided, which only the student can know.
    if school.status in (AppStatus.not_started, AppStatus.in_progress):
        school.status = (AppStatus.in_progress if pct > WEIGHTS["listed"]
                         else AppStatus.not_started)
    session.add(school)
    return pct


def recompute_all(session: Session, user_id: int) -> None:
    """Refresh every school. Cheap enough to run on every screen load, which is
    what keeps the numbers honest without anyone maintaining them."""
    for school in session.exec(
            select(School).where(School.user_id == user_id)).all():
        recompute(session, user_id, school)
    session.commit()


# --------------------------------------------------------------------------
# Deadlines
# --------------------------------------------------------------------------

def days_left(school: School) -> int | None:
    if school.deadline is None:
        return None
    return (school.deadline.date() - utcnow().date()).days


def urgency(school: School) -> str:
    """How loudly the screen should shout about this one."""
    d = days_left(school)
    if d is None:
        return "none"
    if school.status in (AppStatus.submitted, AppStatus.accepted,
                         AppStatus.rejected, AppStatus.waitlisted):
        return "done"
    if d < 0:
        return "passed"
    if d <= 7:
        return "urgent"
    if d <= 30:
        return "soon"
    return "later"


def deadline_phrase(school: School) -> str:
    d = days_left(school)
    if d is None:
        return "No deadline set"
    if d < 0:
        return f"{abs(d)} days ago"
    if d == 0:
        return "Today"
    if d == 1:
        return "Tomorrow"
    if d <= 30:
        return f"{d} days"
    if d <= 60:
        return f"{d // 7} weeks"
    return f"{d // 30} months"


def summary(session: Session, user_id: int) -> dict:
    """Numbers for the top of the applications screen."""
    schools = list(session.exec(
        select(School).where(School.user_id == user_id)).all())
    if not schools:
        return {"count": 0, "average": 0, "submitted": 0, "urgent": 0,
                "next_name": "", "next_when": "", "next_urgency": "none"}

    dated = [s for s in schools if s.deadline is not None
             and urgency(s) not in ("done", "passed")]
    dated.sort(key=lambda s: s.deadline)
    nxt = dated[0] if dated else None

    return {
        "count": len(schools),
        "average": int(round(sum(s.progress for s in schools) / len(schools))),
        "submitted": sum(1 for s in schools
                         if s.status in (AppStatus.submitted, AppStatus.accepted,
                                         AppStatus.rejected, AppStatus.waitlisted)),
        "urgent": sum(1 for s in schools if urgency(s) == "urgent"),
        "next_name": nxt.name if nxt else "",
        "next_when": deadline_phrase(nxt) if nxt else "",
        "next_urgency": urgency(nxt) if nxt else "none",
    }


# ====================================================================
# schools
# ====================================================================

COLUMNS = [("safety", "Safety"), ("reach", "Reach")]


def school_list_for(session: Session, user_id: int) -> list[School]:
    return list(session.exec(
        select(School).where(School.user_id == user_id).order_by(School.name)
    ).all())


def grouped(session: Session, user_id: int) -> dict[str, list[School]]:
    """Schools bucketed by tier, for the Safety / Reach columns."""
    out: dict[str, list[School]] = {t.value: [] for t in Tier}
    for s in school_list_for(session, user_id):
        out.setdefault(s.tier.value, []).append(s)
    return out


def school_add(session: Session, user_id: int, name: str, tier: str = "target",
        deadline: datetime | None = None) -> School:
    name = name.strip()[:120]
    if not name:
        raise ValueError("Give the school a name.")
    school = School(user_id=user_id, name=name,
                    tier=Tier(tier if tier in Tier._value2member_map_ else "target"),
                    deadline=deadline)
    session.add(school)
    session.commit()
    session.refresh(school)
    return school


def school_remove(session: Session, user_id: int, school_id: int) -> None:
    school = session.get(School, school_id)
    if school and school.user_id == user_id:      # ownership check, always
        session.delete(school)
        session.commit()


def set_progress(session: Session, user: User, school_id: int, pct: int) -> None:
    school = session.get(School, school_id)
    if not school or school.user_id != user.id:
        return
    was_done = school.progress >= 100
    school.progress = max(0, min(100, pct))
    if school.progress >= 100 and not was_done:
        school.status = AppStatus.submitted
        profile.award_xp(session, user, 150)      # finishing one is a big deal
    session.add(school)
    session.commit()


def set_status(session: Session, user_id: int, school_id: int, status: str) -> None:
    school = session.get(School, school_id)
    if school and school.user_id == user_id and status in AppStatus._value2member_map_:
        school.status = AppStatus(status)
        session.add(school)
        session.commit()


def next_deadline(session: Session, user_id: int) -> School | None:
    """The soonest unsubmitted deadline — what the home screen counts down to."""
    rows = [s for s in school_list_for(session, user_id)
            if s.deadline and s.status != AppStatus.submitted]
    return min(rows, key=lambda s: s.deadline) if rows else None


# Removed: seed_starter_list(), which filled a new account with six schools
# from the wireframe (NYU, UMich, UCLA, UMD, ASU, CMU). Nothing called it, and
# it should not be called: a student's list is the one thing on this screen
# that is unambiguously theirs, and pre-filling it with somebody else's
# aspirations is both confusing and a little insulting. An empty list now
# earns an honest "Add your first college" from next_task() instead.


# ====================================================================
# essays
# ====================================================================

COACH_STEPS = [
    ("Start with a moment, not a summary.",
     "Drop me into one specific scene. Where were you, what were you doing? "
     "Two sentences is plenty."),
    ("Next, a hook to attract the reader.",
     "Look at your first line. Would a stranger read the second one? If not, "
     "cut everything before the interesting part."),
    ("Now tell me what changed.",
     "Something has to be different by the end — what you believed, what you "
     "noticed, what you decided. Name it plainly."),
    ("Show it instead of claiming it.",
     "Find one sentence that tells me you're hardworking or curious. Replace it "
     "with the thing you actually did."),
    ("Cut a quarter of the words.",
     "Almost every draft is 25% too long. Delete adverbs, throat-clearing, and "
     "anything the reader already worked out."),
    ("Read it aloud, then finish.",
     "If you stumble reading a sentence, so will they. Fix those, and you're done."),
]


def get_or_create(session: Session, user_id: int, school_id: int | None = None,
                  prompt: str = "") -> Essay:
    q = select(Essay).where(Essay.user_id == user_id, Essay.done == False)  # noqa: E712
    if school_id is not None:
        q = q.where(Essay.school_id == school_id)
    essay = session.exec(q).first()
    if essay:
        return essay
    essay = Essay(user_id=user_id, school_id=school_id,
                  prompt=prompt or "Tell us about yourself.")
    session.add(essay)
    session.commit()
    session.refresh(essay)
    return essay


def save_body(session: Session, user_id: int, essay_id: int, body: str) -> int:
    """Save the draft. Returns the word count."""
    essay = session.get(Essay, essay_id)
    if not essay or essay.user_id != user_id:
        return 0
    essay.body = body
    essay.updated_at = utcnow()
    session.add(essay)
    session.commit()
    return word_count(body)


def essay_advance(session: Session, user: User, essay_id: int) -> int:
    """"I'm done!" — move to the next piece of coaching and pay out."""
    essay = session.get(Essay, essay_id)
    if not essay or essay.user_id != user.id:
        return 0
    if essay.step < len(COACH_STEPS) - 1:
        essay.step += 1
        profile.award_xp(session, user, 47)      # the wireframe's ~47 xp
    else:
        essay.done = True
        profile.award_xp(session, user, 120)
    session.add(essay)
    session.commit()
    return essay.step


def word_count(text: str | None) -> int:
    return len((text or "").split())


def step_text(step: int) -> tuple[str, str]:
    return COACH_STEPS[min(step, len(COACH_STEPS) - 1)]


# ====================================================================
# recommenders
# ====================================================================

ROLES = [("teacher", "Teacher recs"), ("guidance", "Guidance")]

# Ordered. Each has the label shown on the chip and the button that advances it.
LADDER = [
    ("not_asked", "Not asked yet", "Mark as asked"),
    ("asked", "Asked", "They said yes"),
    ("agreed", "Agreed", "Letter submitted"),
    ("submitted", "Submitted", None),
]
STATUS_LABEL = {k: label for k, label, _ in LADDER}
NEXT_ACTION = {k: action for k, _, action in LADDER}
_ORDER = [k for k, _, _ in LADDER]



# --------------------------------------------------------------------------
# Today's one task
# --------------------------------------------------------------------------
#
# This replaces a hardcoded string. The home screen used to say
#
#     "Start essay draft for NYU application"   /   "Due in 3 steps  ~47 xp"
#
# to everybody, forever. NYU was a name from the wireframe, "3 steps" was
# invented, and the branch that produced it fired whenever an unfinished essay
# row existed — which is always, because opening the essay screen creates one.
# A student whose list is Rutgers and TCNJ was told to work on NYU.
#
# That is worse than showing nothing. The entire promise of the screen is "here
# is the one thing to do next", and a student who catches it naming a school
# they never typed has no reason to believe the next thing it says either.
#
# So every field below is read from that student's own rows, and when there is
# genuinely nothing to point at, it says so instead of inventing something.


@dataclasses.dataclass
class Task:
    """The one thing on the home screen."""

    title: str
    meta: str
    route: str


def next_task(session: Session, user_id: int) -> Task:
    """The most useful real thing this student could do next.

    Ordered by what actually matters at eleven at night in October: a deadline
    that is about to pass, then an essay that does not exist yet, then an essay
    that is short, then the letters nobody asks for until it is too late.
    """
    schools = list(session.exec(
        select(School).where(School.user_id == user_id)).all())

    # 1. Nothing to work on yet.
    if not schools:
        return Task("Add your first college",
                    "Takes a minute — everything else builds on this",
                    "/applications")

    live = [s for s in schools
            if s.status in (AppStatus.not_started, AppStatus.in_progress)]

    # 2. A deadline inside two weeks beats everything else.
    dated = [s for s in live if days_left(s) is not None and days_left(s) >= 0]
    dated.sort(key=lambda s: days_left(s))
    if dated and days_left(dated[0]) <= 14:
        s = dated[0]
        d = days_left(s)
        when = "due today" if d == 0 else "due tomorrow" if d == 1 else f"{d} days left"
        step = next_step(milestones(session, user_id, s))
        return Task(f"{s.name} is {when}",
                    step.hint if step else f"{s.progress}% done — check what is left",
                    step.route if step else "/applications")

    # 3. An essay that has not been started.
    essays = list(session.exec(
        select(Essay).where(Essay.user_id == user_id)).all())
    by_school = {e.school_id: e for e in essays if e.school_id}
    blank = [s for s in live
             if word_count(by_school.get(s.id).body if by_school.get(s.id) else None) == 0]
    if blank:
        # Soonest deadline first; an undated school is less urgent than a dated one.
        blank.sort(key=lambda s: (days_left(s) is None, days_left(s) or 9999))
        s = blank[0]
        due = deadline_phrase(s)
        return Task(f"Start your {s.name} essay",
                    "Blank page — write it badly first"
                    + (f" · {due}" if s.deadline else ""),
                    "/essays")

    # 4. An essay that is under its own word target.
    short = []
    for s in live:
        e = by_school.get(s.id)
        if e is None:
            continue
        n = word_count(e.body)
        target = e.word_target or 650
        if 0 < n < target:
            short.append((target - n, s, n, target))
    if short:
        short.sort()
        left, s, n, target = short[0]
        return Task(f"Keep going on your {s.name} essay",
                    f"{n} of {target} words — {left} to go", "/essays")

    # 5. Letters, which nobody asks for until it is too late.
    for s in sorted(live, key=lambda x: (days_left(x) is None, days_left(x) or 9999)):
        ms = milestones(session, user_id, s)
        rec = next((m for m in ms if m.key == "recs" and not m.done), None)
        if rec:
            return Task(f"Ask a teacher for your {s.name} letter",
                        rec.detail or rec.hint, rec.route)

    # 6. Whatever is heaviest and still unfinished, anywhere.
    for s in sorted(live, key=lambda x: (days_left(x) is None, days_left(x) or 9999)):
        step = next_step(milestones(session, user_id, s))
        if step:
            return Task(f"{s.name}: {step.label.lower()}", step.hint, step.route)

    # 7. Genuinely nothing outstanding. Say that, rather than inventing work.
    done = sum(1 for s in schools if s.status not in
               (AppStatus.not_started, AppStatus.in_progress))
    if done and done == len(schools):
        return Task("Every application is in",
                    "Nothing to do but wait. That is allowed.", "/applications")
    return Task("Take a breath before you start",
                "Two minutes — the list will still be there", "/meditation")


def rec_list_for(session: Session, user_id: int, role: str | None = None) -> list[Recommender]:
    q = select(Recommender).where(Recommender.user_id == user_id)
    if role:
        q = q.where(Recommender.role == role)
    return list(session.exec(q).all())


def rec_add(session: Session, user_id: int, name: str, subject: str = "",
        role: str = "teacher") -> Recommender:
    name = name.strip()
    if not name:
        raise ValueError("Who are you asking?")
    rec = Recommender(user_id=user_id, name=name[:120], subject=subject.strip()[:60],
                      role=role if role in dict(ROLES) else "teacher")
    session.add(rec)
    session.commit()
    session.refresh(rec)
    return rec


def rec_advance(session: Session, user: User, rec_id: int) -> str:
    """Move one rung up the ladder. XP on the first ask, because that is the
    step that actually takes courage."""
    rec = session.get(Recommender, rec_id)
    if not rec or rec.user_id != user.id:
        return ""
    i = _ORDER.index(rec.status) if rec.status in _ORDER else 0
    if i >= len(_ORDER) - 1:
        return rec.status
    rec.status = _ORDER[i + 1]
    if rec.status == "asked":
        rec.asked_on = utcnow()
        profile.award_xp(session, user, 80)
    elif rec.status == "submitted":
        profile.award_xp(session, user, 60)
    session.add(rec)
    session.commit()
    return rec.status


def rec_remove(session: Session, user_id: int, rec_id: int) -> None:
    rec = session.get(Recommender, rec_id)
    if rec and rec.user_id == user_id:
        session.delete(rec)
        session.commit()
