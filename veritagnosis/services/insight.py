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
from veritagnosis.services import catalog
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
            {"label": "Financial", "score": self.financial_readiness, "icon": "💷"},
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
    next_steps = _rank_next_steps(academic, extracurricular, college_fit, app_progress, financial)

    return ReadinessResult(
        academic=academic,
        extracurricular=extracurricular,
        college_fit=college_fit,
        application_progress=app_progress,
        financial_readiness=financial,
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


def _assess_extracurricular(
    user: User, recs: list[Recommender], checkpoints: list[CheckpointProgress]
) -> int:
    """Leadership, sustained commitment, achievement milestones.

    Scoring:
      - Recommender count = leadership asked for (0 = 0pts, 1-2 = 30pts, 3+ = 60pts)
      - Checkpoint count = sustained commitment (20pts per checkpoint reached, capped at 100)
      - Leadership flag in profile = 20pts (future expansion)
    """
    rec_points = 0
    if len(recs) >= 3:
        rec_points = 60
    elif len(recs) >= 1:
        rec_points = 30

    # Checkpoints = work done: each one signals effort and follow-through
    # 24 total checkpoints; at 20pts each, 5 = 100%
    checkpoint_points = min(100, len(checkpoints) * 20)

    return (rec_points + checkpoint_points) // 2


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


def _explain_academic(user: User, scores: list[TestScore]) -> str:
    """Plain-English explanation of academic score."""
    parts = []
    if user.gpa:
        try:
            parts.append(f"GPA: {user.gpa}")
        except:
            pass

    if scores:
        for s in scores[:2]:  # Top 2
            if s.score:
                parts.append(f"{s.kind}: {s.score}")

    if not parts:
        return "No GPA or test scores entered yet. Schools will want to see both."

    return "Your academic record shows " + ", ".join(parts) + ". Strong foundation."


def _explain_extracurricular(
    user: User, recs: list[Recommender], checkpoints: list[CheckpointProgress]
) -> str:
    """Plain-English explanation of extracurricular score."""
    ach_str = f"You've reached {len(checkpoints)} milestone{'s' if len(checkpoints) != 1 else ''}"

    if len(recs) == 0:
        return f"{ach_str}, but haven't asked for recommendation letters yet. Start asking now."
    elif len(recs) == 1:
        return f"{ach_str} and have 1 recommender lined up. Need 1-2 more."
    else:
        return f"{ach_str} with {len(recs)} recommenders ready to support you."


def _explain_college_fit(schools: list[School]) -> str:
    """Plain-English explanation of college fit score."""
    if not schools:
        return "You haven't added any colleges yet. Start with 5-8 to explore."

    from veritagnosis.models import Tier

    safe = sum(1 for s in schools if s.tier == Tier.safety)
    targ = sum(1 for s in schools if s.tier == Tier.target)
    reach = sum(1 for s in schools if s.tier == Tier.reach)

    balance = ""
    if safe == 0 or reach == 0:
        balance = " ⚠️ Consider adding more " + ("safety schools" if safe == 0 else "reach schools")
    else:
        balance = f" ✓ Good mix: {safe} safety, {targ} target, {reach} reach."

    return f"You're exploring {len(schools)} schools.{balance}"


def _explain_application_progress(
    schools: list[School], essays: list[Essay], recs: list[Recommender]
) -> str:
    """Plain-English explanation of application progress score."""
    done_essays = sum(1 for e in essays if e.done)
    submitted = sum(1 for s in schools if s.status == "submitted")
    ready_recs = sum(1 for r in recs if r.status in ("accepted", "submitted"))

    parts = []
    if done_essays > 0:
        parts.append(f"{done_essays} essay{'s' if done_essays != 1 else ''} written")
    if ready_recs > 0:
        parts.append(f"{ready_recs} recommender{'s' if ready_recs != 1 else ''} ready")
    if submitted > 0:
        parts.append(f"{submitted} application{'s' if submitted != 1 else ''} submitted")

    if not parts:
        return "You haven't started your applications yet. Pick 1-2 schools and draft an essay."

    return "Progress: " + ", ".join(parts) + "."


def _explain_financial_readiness(user: User, schools: list[School]) -> str:
    """Plain-English explanation of financial readiness score."""
    costs_entered = sum(1 for s in schools if s.sticker)
    aid_entered = sum(1 for s in schools if s.aid_offered)

    if costs_entered == 0:
        return "You haven't entered any college costs yet. Look up sticker prices and estimate net cost."

    msg = f"You've researched costs for {costs_entered} college{'s' if costs_entered != 1 else ''}."
    if aid_entered > 0:
        msg += f" {aid_entered} have aid offers recorded."
    else:
        msg += " Next: use the FAFSA simulator to estimate your EFC and aid."

    return msg


# ============================================================================
# BLIND SPOT DETECTION
# ============================================================================


def _detect_blind_spots(
    user: User, schools: list[School], essays: list[Essay], recs: list[Recommender]
) -> list[dict]:
    """Identify what the student hasn't considered yet.

    Returns list of {title, why, action} sorted by importance.
    """
    spots = []

    # Blind spot 1: Not enough colleges researched
    if len(schools) < 5:
        spots.append(
            {
                "icon": "🔍",
                "title": "College research in early stages",
                "why": f"You're exploring {len(schools) or 'no'} schools. Most students aim for 8-12 to find good fits.",
                "action": "Spend 20 min in College Explorer",
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
                    "title": "No safety schools selected",
                    "why": "Having at least 2 schools where you're above-average makes sense. You only have reaches or targets.",
                    "action": "Add 2-3 safety schools",
                    "impact": "College Fit",
                }
            )

    # Blind spot 3: No essays started
    done_essays = sum(1 for e in essays if e.done)
    if done_essays == 0:
        spots.append(
            {
                "icon": "✍️",
                "title": "No essays written yet",
                "why": "You haven't completed any application essays. Most students draft 4-5 (Common App + supplements).",
                "action": "Start your Common App essay",
                "impact": "Application Progress",
            }
        )

    # Blind spot 4: No recommendations sought
    if len(recs) == 0:
        spots.append(
            {
                "icon": "💬",
                "title": "No recommendations arranged",
                "why": "Colleges expect 2-3 recommendation letters. Teachers need 4-6 weeks notice.",
                "action": "Ask 3 teachers today",
                "impact": "Extracurricular",
            }
        )

    # Blind spot 5: No financial planning
    costs = sum(1 for s in schools if s.sticker)
    if costs == 0 and schools:
        spots.append(
            {
                "icon": "💷",
                "title": "Haven't explored college costs",
                "why": "Most families are surprised by net cost vs. sticker price. The FAFSA simulator shows your actual EFC.",
                "action": "Run 3 colleges through the aid simulator",
                "impact": "Financial Readiness",
            }
        )

    return spots


# ============================================================================
# NEXT STEPS RANKING
# ============================================================================


def _rank_next_steps(
    academic: int, extracurricular: int, college_fit: int, app_progress: int, financial: int
) -> list[str]:
    """Rank next steps by impact on readiness.

    Strategy: Work on the lowest-scoring dimension first (biggest impact),
    but don't ignore multiple dimensions (spreads work).
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
        steps.append("Register for your next test → +15 Academic")
    elif lowest == "extracurricular" and extracurricular < 70:
        steps.append("Ask a teacher for a recommendation → +20 Extracurricular")
    elif lowest == "college_fit" and college_fit < 70:
        steps.append("Research 3 new colleges → +15 College Fit")
    elif lowest == "application_progress" and app_progress < 70:
        steps.append("Write your next essay → +15 Application Progress")
    elif lowest == "financial_readiness" and financial < 70:
        steps.append("Run your colleges through the aid simulator → +20 Financial")

    # Second-lowest gets one step
    if len(dims) > 1:
        second = dims[1][0]
        if second == "college_fit":
            steps.append("Explore 3 more colleges on College Search")
        elif second == "application_progress":
            steps.append("Collect another recommendation letter")
        elif second == "financial_readiness":
            steps.append("Submit your FAFSA")

    # If overall is under 50, add a motivational step
    overall = sum(d[1] for d in dims) // len(dims)
    if overall < 50:
        steps.insert(0, "You're in the early stages. Pick one thing and spend 20 minutes on it.")

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
            return f"Your {self.metric} of {_n(self.value)} is below their {band}."
        if self.place == "above":
            return f"Your {self.metric} of {_n(self.value)} is above their {band}."
        return f"Your {self.metric} of {_n(self.value)} is inside their {band}."


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
            f"it is a reach for everyone — most rejected applicants also sit "
            f"inside its published bands."
        )

    if place is None:
        hint = ("Add an SAT or ACT score to compare directly."
                if college.get("sat_25")
                else "This college does not use test scores.")
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
                f"still a target — the band describes the middle, not a cut-off."
            )
        return "reach", (
            f"{stand[0].sentence} With a {rate}% admit rate, treat this as a "
            f"reach and make sure the rest of your list is not all like it."
        )

    if place == "above":
        if rate < NEVER_SAFE_BELOW:
            return "target", (
                f"{stand[0].sentence} That helps, but at a {rate}% admit rate "
                f"no applicant is safe — this is a target, not a safety."
            )
        tier = "safety" if rate >= 50 else "target"
        return tier, f"{stand[0].sentence} Their admit rate is {rate}%."

    # within
    if rate < NEVER_SAFE_BELOW:
        return "reach", (
            f"{stand[0].sentence} Being inside the band is normal for "
            f"applicants here — at a {rate}% admit rate most of them are "
            f"turned down anyway, so this stays a reach."
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
        caveats.append("Sources for this college disagreed; treat these "
                       "numbers as rough and check the college's own site.")
    elif entry.get("confidence") == "medium":
        caveats.append("These figures come from a secondary source, not the "
                       "college's own published data set.")

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
        warnings.append("Everything on your list is a reach — worth adding one "
                        "where your numbers already clear the bar.")
    elif known and by_tier["safety"] == 0:
        warnings.append("No safety on your list yet.")

    if not stats["sat"] and not stats["act"]:
        warnings.append("Add an SAT or ACT score to sharpen these.")
    if stats["gpa"] is None:
        warnings.append("Add your GPA to include it.")

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
