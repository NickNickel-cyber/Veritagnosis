"""
What the student's data adds up to: readiness across five
dimensions, fit against colleges' published intake, and the
profile that feeds both.

Merged from: readiness, fit, profile.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime
from sqlmodel import select
from veritagnosis import db
from veritagnosis.content.achievements import ACHIEVEMENTS
from veritagnosis.models import (
    CheckpointProgress,
    Essay,
    MeditationLog,
    Recommender,
    School,
    TestScore,
    User,
    utcnow,
)
from veritagnosis.content.colleges import BY_NAME, COLLEGES
from veritagnosis.services import activities, catalog
from veritagnosis.models import School, TestScore, Tier, User
import json
from datetime import timedelta
from sqlmodel import Session
from veritagnosis.models import User, utcnow


# ====================================================================
# readiness
# ====================================================================

@dataclasses.dataclass
class ReadinessResult:
    """Five-dimension readiness score with explanations and next steps."""

    academic: int  # GPA and test scores
    extracurricular: int  # Leadership and commitment
    college_fit: int  # Number, tier distribution, research
    application_progress: int  # Essays, recs, submissions
    financial_readiness: int  # Aid forms, cost planning

    explanations: dict[str, str]  # Why each score is what it is
    blind_spots: list[dict]  # Things the student hasn't looked at
    next_steps: list[str]  # Ordered by impact

    @property
    def overall(self) -> int:
        """Average of five dimensions."""
        dims = [
            self.academic,
            self.extracurricular,
            self.college_fit,
            self.application_progress,
            self.financial_readiness,
        ]
        return sum(dims) // len(dims)

    def dashboard_sections(self) -> list[dict]:
        """Format for dashboard display."""
        return [
            {"label": "Academic", "score": self.academic, "icon": "🎓"},
            {"label": "Extracurricular", "score": self.extracurricular, "icon": "🌟"},
            {"label": "College Fit", "score": self.college_fit, "icon": "🎯"},
            {"label": "Application", "score": self.application_progress, "icon": "📝"},
            {"label": "Financial", "score": self.financial_readiness, "icon": "💵"},
        ]


def assess(uid: int) -> ReadinessResult:
    """Calculate readiness for one student. Deterministic, always same data → same score."""
    with db.get_session() as s:
        user = s.get(User, uid)
        if not user:
            raise ValueError(f"User {uid} not found")

        schools = s.exec(select(School).where(School.user_id == uid)).all()
        scores = s.exec(select(TestScore).where(TestScore.user_id == uid)).all()
        essays = s.exec(select(Essay).where(Essay.user_id == uid)).all()
        recs = s.exec(select(Recommender).where(Recommender.user_id == uid)).all()
        checkpoints = s.exec(
            select(CheckpointProgress).where(CheckpointProgress.user_id == uid)
        ).all()

    academic = _assess_academic(user, scores)
    extracurricular = _assess_extracurricular(user, recs, checkpoints)
    college_fit = _assess_college_fit(schools)
    app_progress = _assess_application_progress(schools, essays, recs)
    financial = _assess_financial_readiness(user, schools)

    explanations = {
        "academic": _explain_academic(user, scores),
        "extracurricular": _explain_extracurricular(user, recs, checkpoints),
        "college_fit": _explain_college_fit(schools),
        "application_progress": _explain_application_progress(schools, essays, recs),
        "financial_readiness": _explain_financial_readiness(user, schools),
    }

    blind_spots = _detect_blind_spots(user, schools, essays, recs)
    next_steps = _rank_next_steps(academic, extracurricular, college_fit, app_progress,
                                  financial, _activity_rows(user))

    # Whole numbers, always. One of the scorers works in fractions, and a
    # float leaking out of here reached an int field on the profile screen
    # ("Expected field 'readiness_overall' to receive type int, got 51.0").
    return ReadinessResult(
        academic=int(round(academic)),
        extracurricular=int(round(extracurricular)),
        college_fit=int(round(college_fit)),
        application_progress=int(round(app_progress)),
        financial_readiness=int(round(financial)),
        explanations=explanations,
        blind_spots=blind_spots,
        next_steps=next_steps,
    )


# ============================================================================
# DIMENSION SCORING
# ============================================================================


def _assess_academic(user: User, scores: list[TestScore]) -> int:
    """GPA and test scores. No GPA = 50 (middle ground). No scores = 40."""
    gpa_points = 0
    test_points = 0

    # GPA: encrypt on model but we decrypt when reading
    if user.gpa:
        try:
            gpa = float(user.gpa)
            # 4.0 = 100, 3.5 = 85, 3.0 = 70, 2.5 = 55, 2.0 = 40, below 2.0 = 30
            gpa_points = max(30, min(100, int((gpa / 4.0) * 100)))
        except (ValueError, TypeError):
            gpa_points = 50  # Unable to parse = neutral

    # Test scores: SAT 1400+ = 90, 1300 = 80, 1200 = 70, below 1000 = 40
    # ACT 34+ = 90, 32 = 80, 30 = 70, below 28 = 40
    if scores:
        test_points = 50  # Start neutral if we have scores
        # The BEST score counts, not the last one the database happened to
        # return. Assigning inside this loop (as this once did) meant a student
        # with a 1550 SAT and a weak practice ACT was scored on whichever row
        # came back second — and since the query has no ORDER BY, two calls on
        # identical data could disagree, which broke the determinism this
        # module promises.
        for score in scores:
            if not score.score:
                continue
            try:
                val = int(str(score.score).strip())
            except (ValueError, TypeError, AttributeError):
                continue
            kind = (score.kind or "").strip().upper()
            # Reject values off the real scale so one typo cannot dominate.
            if kind == "SAT" and 400 <= val <= 1600:
                test_points = max(test_points,
                                  max(40, min(100, (val - 800) // 6)))
            elif kind == "ACT" and 1 <= val <= 36:
                test_points = max(test_points,
                                  max(40, min(100, int((val - 15) * 3.33))))

    # Average GPA and tests; if no GPA, just use tests
    if user.gpa:
        return (gpa_points + test_points) // 2 if test_points > 0 else gpa_points
    return test_points if test_points > 0 else 50


def _activity_rows(user: User) -> list[dict]:
    """The activities on the student's profile. An unreadable profile is the
    same as an empty one here: the profile screen says so and offers a fix."""
    try:
        return activities.parse(user.profile_data)
    except Exception:                                          # noqa: BLE001
        return []


def _assess_extracurricular(
    user: User, recs: list[Recommender], checkpoints: list[CheckpointProgress]
) -> int:
    """The student's activities: intensity, years, leadership, and what the
    names say about them. See services/activities.py for every rule.

    This used to be recommenders and app checkpoints, which measured how much
    of this app had been used rather than anything a college would read.
    `recs` and `checkpoints` are still accepted so callers need not change;
    recommenders count under Applications instead.
    """
    return activities.score(_activity_rows(user))


def _assess_college_fit(schools: list[School]) -> int:
    """Number of colleges, tier distribution, research depth.

    Scoring:
      - 0 colleges = 0
      - 1-3 colleges = 25 + (count * 15)
      - 4-6 colleges = 50 + (count * 8)
      - 7-10 colleges = 80 + (count * 2)
      - 11+ = 95-100
      - Tier distribution: -10 if all safety, -10 if all reach, balanced = +10
      - Notes present = research depth: +5 per college with notes
    """
    if not schools:
        return 0

    count = len(schools)
    base = 0
    if count <= 3:
        base = 25 + (count * 15)
    elif count <= 6:
        base = 50 + (count * 8)
    elif count <= 10:
        base = 80 + (count * 2)
    else:
        base = 95 + min(5, (count - 10))

    # Tier distribution
    from veritagnosis.models import Tier
    safety_count = sum(1 for s in schools if s.tier == Tier.safety)
    reach_count = sum(1 for s in schools if s.tier == Tier.reach)
    target_count = sum(1 for s in schools if s.tier == Tier.target)

    tier_bonus = 0
    if safety_count > 0 and reach_count > 0 and target_count > 0:
        tier_bonus = 10  # Balanced
    elif safety_count == 0 or (reach_count == 0 and target_count == 0):
        tier_bonus = -10  # All one type

    # Research depth: notes = student researched this school
    notes_bonus = sum(5 for s in schools if s.notes) if schools else 0

    return min(100, base + tier_bonus + notes_bonus)


def _assess_application_progress(
    schools: list[School], essays: list[Essay], recs: list[Recommender]
) -> int:
    """Essays written, recommendations collected, applications submitted.

    Scoring based on typical timeline:
      - Essays: expect 4 total (Common App + 3 supplemental)
        1 essay = 25%, 2 = 50%, 3 = 75%, 4+ = 100%
      - Recommendations: expect 2-3
        1 rec = 25%, 2 = 60%, 3 = 90%
      - Applications: expect 5-8
        1 submitted = 20%, 2 = 40%, 3 = 60%, 5 = 80%, 8+ = 100%

    Default assumption (if no schools): generous credit for any essay/rec work
    """
    essay_score = 0
    if essays:
        # Done essays: only count if done=True
        done_count = sum(1 for e in essays if e.done)
        essay_score = min(100, (done_count / 4) * 100)

    rec_score = 0
    if recs:
        # "agreed" is the real status for a teacher who has said yes; there is
        # no "accepted" anywhere in the app's vocabulary (see
        # services/recommenders.py STATUS_FLOW), so the old check matched
        # nothing and told students with every letter lined up that they had
        # none.
        ready_count = sum(1 for r in recs if r.status in ("agreed", "submitted"))
        rec_score = min(100, (ready_count / 2) * 100)

    submitted_count = sum(1 for s in schools if s.status == "submitted")
    app_score = 0
    if schools:
        app_score = min(100, (submitted_count / 5) * 100)
    elif submitted_count > 0:
        app_score = 50  # Submitted but no schools tracked = partial credit

    return (essay_score + rec_score + app_score) // 3


def _assess_financial_readiness(user: User, schools: list[School]) -> int:
    """Aid form submission, cost understanding, affordability planning.

    Scoring:
      - FAFSA started: 30pts (future: check profile.fafsa_status)
      - Colleges with costs entered: 20pts each, capped at 60
      - Colleges with affordability analysis: 10pts each, capped at 30
      - Default: 40 (some thought given)
    """
    # For now: heuristic from schools
    # Schools with net_cost or sticker = student looked at costs
    cost_count = sum(1 for s in schools if s.sticker or s.net_cost)
    cost_points = min(60, cost_count * 20)

    # Colleges where aid was offered = deeper analysis
    aid_count = sum(1 for s in schools if s.aid_offered)
    aid_points = min(30, aid_count * 10)

    base = 40 if not schools else 30
    return min(100, base + cost_points + aid_points)


# ============================================================================
# EXPLANATIONS
# ============================================================================


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _explain_academic(user: User, scores: list[TestScore]) -> str:
    """Plain-English explanation of academic score."""
    parts = []
    if user.gpa:
        parts.append(f"GPA {user.gpa}")

    if scores:
        for s in scores[:2]:  # Top 2
            if s.score:
                parts.append(f"{s.kind} {s.score}")

    if not parts:
        return ("No GPA or test scores yet. Add them so each college can be "
                "compared with your numbers.")

    # No verdict on whether the numbers are good: that depends entirely on
    # which colleges they are being held up against, and the fit cards below
    # say exactly that, college by college.
    return "Your numbers so far: " + ", ".join(parts) + "."


def _explain_extracurricular(
    user: User, recs: list[Recommender], checkpoints: list[CheckpointProgress]
) -> str:
    """Plain-English explanation of the activities score."""
    return activities.explain(_activity_rows(user))


def _explain_college_fit(schools: list[School]) -> str:
    """Plain-English explanation of college fit score."""
    if not schools:
        return ("You haven't added any colleges yet. Start with a few you're "
                "curious about.")

    from veritagnosis.models import Tier

    safe = sum(1 for s in schools if s.tier == Tier.safety)
    targ = sum(1 for s in schools if s.tier == Tier.target)
    reach = sum(1 for s in schools if s.tier == Tier.reach)

    if safe == 0:
        balance = " You don't have a safety school yet."
    elif reach == 0:
        balance = " You don't have any reach schools yet."
    else:
        balance = f" A good mix: {safe} safety, {targ} target, {reach} reach."

    return f"You have {_plural(len(schools), 'college')} on your list.{balance}"


def _explain_application_progress(
    schools: list[School], essays: list[Essay], recs: list[Recommender]
) -> str:
    """Plain-English explanation of application progress score."""
    done_essays = sum(1 for e in essays if e.done)
    submitted = sum(1 for s in schools if s.status == "submitted")
    ready_recs = sum(1 for r in recs if r.status in ("accepted", "submitted"))

    parts = []
    if done_essays > 0:
        parts.append(f"{_plural(done_essays, 'essay')} written")
    if ready_recs > 0:
        parts.append(f"{_plural(ready_recs, 'recommender')} ready")
    if submitted > 0:
        parts.append(f"{_plural(submitted, 'application')} submitted")

    if not parts:
        return ("You haven't started any applications yet. Pick one school and "
                "start an essay.")

    return "So far: " + ", ".join(parts) + "."


def _explain_financial_readiness(user: User, schools: list[School]) -> str:
    """Plain-English explanation of financial readiness score."""
    costs_entered = sum(1 for s in schools if s.sticker)
    aid_entered = sum(1 for s in schools if s.aid_offered)

    if costs_entered == 0:
        return ("You haven't added any college costs yet. Start with the net "
                "price calculator on each college's website.")

    msg = f"You've added costs for {_plural(costs_entered, 'college')}."
    if aid_entered > 0:
        msg += (f" {aid_entered} {'has an aid offer' if aid_entered == 1 else 'have aid offers'}"
                f" recorded.")
    else:
        msg += " Next, try the aid simulator to estimate your Student Aid Index."

    return msg


# ============================================================================
# BLIND SPOT DETECTION
# ============================================================================


def _detect_blind_spots(
    user: User, schools: list[School], essays: list[Essay], recs: list[Recommender]
) -> list[dict]:
    """Identify what the student hasn't considered yet.

    Returns list of {title, why, action} sorted by importance.

    None of these quote what "most students" do. Those figures vary by school,
    by year and by who is counting, and a number the app cannot source is a
    number it should not be showing a seventeen-year-old as fact.
    """
    spots = []

    # Blind spot 1: Not enough colleges researched
    if len(schools) < 5:
        n = len(schools)
        spots.append(
            {
                "icon": "🔍",
                "title": "Your college list is still short",
                "why": (f"You have {_plural(n, 'college') if n else 'no colleges'} "
                        f"on your list. A few more gives you real choices in the "
                        f"spring."),
                "action": "Add a few more colleges",
                "impact": "College Fit",
            }
        )

    # Blind spot 2: No safety schools
    from veritagnosis.models import Tier
    if schools:
        safety = sum(1 for s in schools if s.tier == Tier.safety)
        if safety == 0:
            spots.append(
                {
                    "icon": "⚠️",
                    "title": "No safety schools yet",
                    "why": ("A safety is a school where your numbers are well "
                            "above its usual range. One or two means you'll have "
                            "options no matter what."),
                    "action": "Add a safety school or two",
                    "impact": "College Fit",
                }
            )

    # Blind spot 3: No essays started
    done_essays = sum(1 for e in essays if e.done)
    if done_essays == 0:
        spots.append(
            {
                "icon": "✍️",
                "title": "No essays finished yet",
                "why": ("Most applications need a personal statement, and many "
                        "add a few shorter supplements on top."),
                "action": "Start your Common App essay",
                "impact": "Application Progress",
            }
        )

    # Blind spot 4: No activities on the profile
    if not _activity_rows(user):
        spots.append(
            {
                "icon": "🏅",
                "title": "No activities on your profile yet",
                "why": ("Clubs, sports, jobs, volunteering and anything else you "
                        "put real time into all count. So does leading any of "
                        "them."),
                "action": "Add your activities",
                "impact": "Extracurricular",
            }
        )

    # Blind spot 5: No recommendations sought
    if len(recs) == 0:
        spots.append(
            {
                "icon": "💬",
                "title": "No recommenders yet",
                "why": ("Many colleges ask for teacher letters, and teachers need "
                        "a few weeks' notice to write a good one."),
                "action": "Ask a teacher this week",
                "impact": "Application Progress",
            }
        )

    # Blind spot 6: No financial planning
    costs = sum(1 for s in schools if s.sticker)
    if costs == 0 and schools:
        spots.append(
            {
                "icon": "💵",
                "title": "You haven't looked at costs yet",
                "why": ("The sticker price is often very different from what a "
                        "family actually pays. The aid simulator gives you a "
                        "rough idea of yours."),
                "action": "Try the aid simulator",
                "impact": "Financial Readiness",
            }
        )

    return spots


# ============================================================================
# NEXT STEPS RANKING
# ============================================================================


def _rank_next_steps(
    academic: int, extracurricular: int, college_fit: int, app_progress: int, financial: int,
    activity_rows: list[dict] | None = None,
) -> list[str]:
    """Rank next steps by impact on readiness.

    Strategy: Work on the lowest-scoring dimension first (biggest impact),
    but don't ignore multiple dimensions (spreads work).

    These used to end in a points promise ("→ +15 Academic"). The scores are
    worked out from the student's own rows, so no fixed number was ever true;
    each step now says only what to do.
    """
    dims = [
        ("academic", academic),
        ("extracurricular", extracurricular),
        ("college_fit", college_fit),
        ("application_progress", app_progress),
        ("financial_readiness", financial),
    ]

    # Sort by score ascending (lowest first = most impact)
    dims.sort(key=lambda x: x[1])

    steps = []

    # The lowest-scoring dimension gets 2 steps
    lowest = dims[0][0]
    if lowest == "academic" and academic < 70:
        steps.append("Add your GPA and any test scores you have")
    elif lowest == "extracurricular" and extracurricular < 70:
        steps.append(activities.tip(activity_rows or []))
    elif lowest == "college_fit" and college_fit < 70:
        steps.append("Add a few more colleges to your list")
    elif lowest == "application_progress" and app_progress < 70:
        steps.append("Work on your next essay")
    elif lowest == "financial_readiness" and financial < 70:
        steps.append("Run your colleges through the aid simulator")

    # Second-lowest gets one step
    if len(dims) > 1:
        second = dims[1][0]
        if second == "college_fit":
            steps.append("Look into a few more colleges")
        elif second == "application_progress":
            steps.append("Line up a teacher recommendation")
        elif second == "extracurricular":
            steps.append(activities.tip(activity_rows or []))
        elif second == "financial_readiness":
            steps.append("File your FAFSA")

    # If overall is under 50, add a motivational step
    overall = sum(d[1] for d in dims) // len(dims)
    if overall < 50:
        steps.insert(0, "You're just getting started. Pick one thing and give it 20 minutes.")

    return steps[:3]  # Top 3 next steps


# ====================================================================
# fit
# ====================================================================

NEVER_SAFE_BELOW = 20.0
REACH_FLOOR = 10.0


@dataclasses.dataclass
class Standing:
    """Where one number sits against one published band."""

    metric: str          # "SAT" | "ACT" | "GPA"
    value: float
    low: float
    high: float

    @property
    def place(self) -> str:
        if self.value < self.low:
            return "below"
        if self.value > self.high:
            return "above"
        return "within"

    @property
    def sentence(self) -> str:
        band = f"{_n(self.low)}–{_n(self.high)}"
        if self.place == "below":
            return f"Your {self.metric} of {_n(self.value)} is below their usual range of {band}."
        if self.place == "above":
            return f"Your {self.metric} of {_n(self.value)} is above their usual range of {band}."
        return f"Your {self.metric} of {_n(self.value)} is inside their usual range of {band}."


@dataclasses.dataclass
class Fit:
    """One college on the student's list, measured against what it published."""

    school_name: str
    student_tier: str            # what the student called it
    data_tier: str | None        # what the published data says, or None
    standings: list[Standing]
    accept_rate: float | None
    cost_year: int | None
    data_year: str
    source_url: str
    confidence: str
    caveats: list[str]
    has_data: bool
    # Which row this is, and — when the name was not recognised — the full
    # names it might be, so the screen can offer a one-tap fix.
    school_id: int = 0
    suggestions: list[str] = dataclasses.field(default_factory=list)

    @property
    def disagrees(self) -> bool:
        """The student's label is more optimistic than the data supports."""
        if not self.has_data or self.data_tier is None:
            return False
        rank = {"safety": 0, "target": 1, "reach": 2}
        return rank[self.student_tier] < rank[self.data_tier]


def _n(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:.2f}"


def student_stats(uid: int) -> dict:
    """The student's own numbers, best available of each kind.

    Both GPA and scores are encrypted at rest and arrive as strings, and a
    student may have typed anything at all into them. Everything that will not
    parse is dropped rather than guessed at.
    """
    out: dict = {"gpa": None, "sat": None, "act": None}
    with db.get_session() as s:
        user = s.get(User, uid)
        if user and user.gpa:
            try:
                g = float(str(user.gpa).strip())
                if 0.0 <= g <= 5.0:
                    out["gpa"] = g
            except (TypeError, ValueError):
                pass

        rows = s.exec(select(TestScore).where(TestScore.user_id == uid)).all()

    for r in rows:
        kind = (r.kind or "").strip().upper()
        try:
            v = int(float(str(r.score).strip()))
        except (TypeError, ValueError, AttributeError):
            continue
        # Keep the best of each, and reject values outside the real scale so a
        # typo cannot place someone above every college in the country.
        if kind == "SAT" and 400 <= v <= 1600:
            out["sat"] = max(out["sat"] or 0, v)
        elif kind == "ACT" and 1 <= v <= 36:
            out["act"] = max(out["act"] or 0, v)
    return out


def _standings(college: dict, stats: dict) -> list[Standing]:
    found: list[Standing] = []
    if stats["sat"] and college.get("sat_25") and college.get("sat_75"):
        found.append(Standing("SAT", stats["sat"],
                              college["sat_25"], college["sat_75"]))
    if stats["act"] and college.get("act_25") and college.get("act_75"):
        found.append(Standing("ACT", stats["act"],
                              college["act_25"], college["act_75"]))
    return found


def classify(college: dict, stats: dict) -> tuple[str | None, str]:
    """Reach / target / safety from the published data, with the reasoning.

    Selectivity sets a floor that a strong applicant cannot argue their way
    below, because at these admit rates the published bands stop being
    predictive — most rejected applicants are inside them too.
    """
    rate = college.get("accept_rate")
    if rate is None:
        return None, "No published admit rate for this college yet."

    stand = _standings(college, stats)
    place = stand[0].place if stand else None

    if rate < REACH_FLOOR:
        return "reach", (
            f"{college['name']} admitted {rate}% of applicants. At that rate "
            f"it's a reach for everyone. Most of the students it turns down "
            f"have scores inside its usual range too."
        )

    if place is None:
        hint = ("Add an SAT or ACT score to compare directly."
                if college.get("sat_25")
                else "This college doesn't publish test score ranges.")
        tier = "reach" if rate < 30 else "target" if rate < 60 else "safety"
        return tier, f"Based on its {rate}% admit rate alone. {hint}"

    if place == "below":
        # Below the band means below most admitted students — but at a college
        # taking nearly half its applicants that is a long way from unlikely.
        # Treating every below-band college as a reach regardless of admit rate
        # would flatten the list into one undifferentiated wall of red and make
        # the genuinely long shots impossible to pick out.
        if rate >= 40:
            return "target", (
                f"{stand[0].sentence} They admit {rate}% though, so this is "
                f"still a target. The range shows the middle of admitted "
                f"students, not a cutoff."
            )
        return "reach", (
            f"{stand[0].sentence} With a {rate}% admit rate, treat this as a "
            f"reach and make sure the rest of your list isn't all like it."
        )

    if place == "above":
        if rate < NEVER_SAFE_BELOW:
            return "target", (
                f"{stand[0].sentence} That helps, but at a {rate}% admit rate "
                f"no applicant is a sure thing, so this is a target, not a "
                f"safety."
            )
        tier = "safety" if rate >= 50 else "target"
        return tier, f"{stand[0].sentence} Their admit rate is {rate}%."

    # within
    if rate < NEVER_SAFE_BELOW:
        return "reach", (
            f"{stand[0].sentence} Most applicants here are inside the range "
            f"too, and at a {rate}% admit rate most of them still get turned "
            f"down, so this stays a reach."
        )
    tier = "target" if rate < 60 else "safety"
    return tier, f"{stand[0].sentence} Their admit rate is {rate}%."


def for_school(school: School, stats: dict, session: Session | None = None) -> Fit:
    """Measure one school on the student's list.

    `session` is optional so the two dozen curated colleges still work with no
    database at all (and so the existing tests keep calling this with two
    arguments). When it is supplied, a school that is not in the curated file
    is looked up in the imported College Scorecard catalogue instead of being
    reported as "no data" — which, before the import existed, was the answer
    for almost every school a real student actually types.
    """
    entry = catalog.lookup(session, school.name or "")
    student_tier = school.tier.value if hasattr(school.tier, "value") else str(school.tier)

    if entry is None:
        options = [c["name"] for c in catalog.suggest(session, school.name or "", 3)]
        return Fit(school_name=school.name, student_tier=student_tier,
                   data_tier=None, standings=[], accept_rate=None,
                   cost_year=None, data_year="", source_url="",
                   confidence="", caveats=[], has_data=False,
                   school_id=school.id or 0, suggestions=options)

    tier, why = classify(entry, stats)

    caveats: list[str] = []
    if entry.get("test_optional_note"):
        caveats.append(entry["test_optional_note"])
    if entry.get("note"):
        caveats.append(entry["note"])
    if entry.get("confidence") == "low":
        caveats.append(("Sources for this college disagree, so treat these numbers as rough "
                        "and check the college's own website."))
    elif entry.get("confidence") == "medium":
        caveats.append(("These numbers come from a secondary source, not the college's own "
                        "report."))

    return Fit(
        school_name=school.name,
        student_tier=student_tier,
        data_tier=tier,
        standings=_standings(entry, stats),
        accept_rate=entry.get("accept_rate"),
        cost_year=entry.get("cost_year"),
        data_year=entry.get("data_year", ""),
        source_url=entry.get("source_url", ""),
        confidence=entry.get("confidence", ""),
        caveats=[c for c in caveats if c],
        has_data=True,
        school_id=school.id or 0,
    )


def review(uid: int) -> dict:
    """The whole list, measured.

    Returns the per-college fits plus the two list-level facts that matter more
    than any single college: whether anything on the list is actually within
    reach, and where the student's own labels disagree with the data.
    """
    stats = student_stats(uid)
    with db.get_session() as s:
        # Nicknames saved before names were checked become full names first,
        # so a list holding "UMich" is measured as Michigan, not as no data.
        catalog.tidy_names(s, uid)
        schools = list(s.exec(select(School).where(School.user_id == uid)).all())

    with db.get_session() as s:
        fits = [for_school(sc, stats, s) for sc in schools]
    known = [f for f in fits if f.has_data and f.data_tier]

    by_tier = {"reach": 0, "target": 0, "safety": 0}
    for f in known:
        by_tier[f.data_tier] += 1

    warnings: list[str] = []

    # What this block used to be, and why it is short now.
    #
    # It carried four paragraphs. The longest explained, at length, that the
    # app could not judge safety coverage "because every college loaded here
    # admits under half its applicants — this is a gap in our data, not a
    # verdict on your list", and another recited how many universities were
    # loaded and what range of admit rates they spanned.
    #
    # Both were honest and both were written for a catalogue of two dozen
    # colleges. With the Scorecard import there are thousands, including plenty
    # of genuinely accessible ones, so the gap those paragraphs apologised for
    # is gone — and a student reading a statistics box does not want a
    # paragraph about the provenance of the dataset. What is left is only the
    # lines that tell them to do something.
    if known and by_tier["safety"] == 0 and by_tier["target"] == 0:
        warnings.append((("Everything on your list is a reach, so try adding one where your "
                          "numbers are above the usual range.")))
    elif known and by_tier["safety"] == 0:
        warnings.append("No safety on your list yet.")

    if not stats["sat"] and not stats["act"]:
        warnings.append("Add an SAT or ACT score to make these more accurate.")
    if stats["gpa"] is None:
        warnings.append("Add your GPA so it's included too.")

    return {
        "stats": stats,
        "fits": fits,
        "by_tier": by_tier,
        "disagreements": [f for f in fits if f.disagrees],
        "no_data": [f for f in fits if not f.has_data],
        "warnings": warnings,
    }


# ====================================================================
# profile
# ====================================================================

XP_PER_LEVEL = 500


def level_for(xp: int) -> int:
    return 1 + xp // XP_PER_LEVEL


def xp_into_level(xp: int) -> int:
    return xp % XP_PER_LEVEL


def award_xp(session: Session, user: User, amount: int) -> tuple[int, bool]:
    """Add XP. Returns (new_level, levelled_up) so the caller can celebrate."""
    before = level_for(user.xp)
    user.xp = max(0, user.xp + amount)
    after = level_for(user.xp)
    session.add(user)
    session.commit()
    return after, after > before


def touch_streak(session: Session, user: User) -> int:
    """Call once per day of activity.

    Same day: nothing. Yesterday: extend. Longer ago: reset to 1. Keeping this
    in one function is what stops the streak being counted twice by two
    different screens on the same day.
    """
    today = utcnow().date()
    last = user.last_active.date() if user.last_active else None
    if last == today:
        return user.streak_days
    user.streak_days = user.streak_days + 1 if last == today - timedelta(days=1) else 1
    user.last_active = utcnow()
    session.add(user)
    session.commit()
    return user.streak_days


def save_avatar(session: Session, user: User, selection: dict) -> None:
    """Avatar is a small JSON blob of part indexes, not its own table — it is
    always read and written whole, so a table would be five joins for nothing."""
    user.avatar = json.dumps(selection)[:512]
    session.add(user)
    session.commit()


def load_avatar(user: User) -> dict:
    try:
        return json.loads(user.avatar or "{}")
    except (ValueError, TypeError):
        return {}


def set_theme(session: Session, user: User, theme: str) -> None:
    user.theme = theme[:20]
    session.add(user)
    session.commit()
