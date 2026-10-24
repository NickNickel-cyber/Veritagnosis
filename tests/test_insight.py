"""
The two engines that judge a student's position: readiness across five
dimensions, and fit against what colleges actually published.

Most of the fit tests are about restraint — the ways the engine could
mislead someone are all worse than the ways it could be imprecise.

Merged from: test_readiness, test_fit.
"""
from __future__ import annotations

import uuid
import pytest
from sqlmodel import select
from veritagnosis import db
from veritagnosis.models import (
    CheckpointProgress,
    Essay,
    Recommender,
    School,
    TestScore,
    User,
    utcnow,
    Tier,
    AppStatus,
)
from veritagnosis.services.insight import (
    ReadinessResult,
    assess,
    _assess_academic,
    _assess_extracurricular,
    _assess_college_fit,
    _assess_application_progress,
    _assess_financial_readiness,
)
from veritagnosis.content.colleges import BY_NAME, COLLEGES
from veritagnosis.models import AppStatus, School, TestScore, Tier, User
from veritagnosis.services import insight as fit


# ====================================================================
# from test_readiness.py
# ====================================================================

def _unique_username(prefix="test"):
    """Generate a unique username."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_user():
    """Create a test user with minimal data."""
    with db.get_session() as s:
        u = User(username=_unique_username("readiness"), password_hash="xxx")
        s.add(u)
        s.commit()
        s.refresh(u)
        uid = u.id
    # Return just the ID since the user object is detached after session closes
    return uid


def test_readiness_result_overall_score():
    """Overall score is average of five dimensions."""
    r = ReadinessResult(
        academic=80,
        extracurricular=60,
        college_fit=70,
        application_progress=90,
        financial_readiness=50,
        explanations={},
        blind_spots=[],
        next_steps=[],
    )
    # (80 + 60 + 70 + 90 + 50) / 5 = 70
    assert r.overall == 70


def test_readiness_is_deterministic(test_user):
    """Same data always yields same score."""
    # test_user is already a user_id from fixture
    # Add same data twice
    with db.get_session() as s:
        s.add(TestScore(user_id=test_user, kind="SAT", score="1400"))
        s.commit()

    r1 = assess(test_user)
    r2 = assess(test_user)

    assert r1.academic == r2.academic
    assert r1.overall == r2.overall


def test_academic_score_requires_gpa_or_test():
    """No GPA, no test = 50 (neutral); just GPA scores higher."""
    # This is tested implicitly through assess, but document the behavior
    u1 = User(username=_unique_username("no_scores"), password_hash="x")
    u2 = User(username=_unique_username("gpa_only"), password_hash="x")

    with db.get_session() as s:
        s.add(u1)
        s.add(u2)
        s.commit()
        s.refresh(u1)
        s.refresh(u2)

        # u1: no scores
        r1_academic = _assess_academic(u1, [])
        assert r1_academic == 50  # Neutral

        # u2: GPA = 3.5 → should be 87
        u2.gpa = "3.5"
        r2_academic = _assess_academic(u2, [])
        assert r2_academic > 50


def test_extracurricular_score_comes_from_activities_not_app_use():
    """Checkpoints measure how much of this app was used, which no college
    reads. The Activities score is built from the profile's activities."""
    import json
    user = User(username=_unique_username("test_checkpoints"), password_hash="x")
    with db.get_session() as s:
        s.add(user)
        s.commit()
        s.refresh(user)
        for i in range(3):
            s.add(CheckpointProgress(user_id=user.id, checkpoint_key=f"a_test_{i}"))
        s.commit()
        checkpoints = s.exec(
            select(CheckpointProgress).where(CheckpointProgress.user_id == user.id)
        ).all()

    assert _assess_extracurricular(user, [], checkpoints) == 0

    user.profile_data = json.dumps({"extracurriculars": [
        {"name": "Varsity soccer captain", "intensity": "intense",
         "years": "3", "leadership": "no"}]})
    assert _assess_extracurricular(user, [], checkpoints) > 30


def test_college_fit_zero_schools():
    """No colleges = 0 points."""
    score = _assess_college_fit([])
    assert score == 0


def test_college_fit_balanced_distribution():
    """Balanced tier distribution (safety, target, reach) = bonus."""
    user = User(username=_unique_username("test_fit"), password_hash="x")
    with db.get_session() as s:
        s.add(user)
        s.commit()
        s.refresh(user)

        # 3 schools: 1 safety, 1 target, 1 reach
        for tier in [Tier.safety, Tier.target, Tier.reach]:
            s.add(
                School(
                    user_id=user.id,
                    name=f"School-{tier}",
                    tier=tier,
                    status=AppStatus.not_started,
                )
            )
        s.commit()

        schools = s.exec(select(School).where(School.user_id == user.id)).all()

    score = _assess_college_fit(schools)
    # Base: 3 schools = 25 + (3 * 15) = 70
    # Balanced distribution = +10
    # So around 80
    assert score >= 75


def test_college_fit_all_one_tier():
    """All safety or all reach = penalty."""
    user = User(username=_unique_username("test_fit_penalty"), password_hash="x")
    with db.get_session() as s:
        s.add(user)
        s.commit()
        s.refresh(user)

        # 3 schools: all reach
        for i in range(3):
            s.add(
                School(
                    user_id=user.id,
                    name=f"Reach-{i}",
                    tier=Tier.reach,
                    status=AppStatus.not_started,
                )
            )
        s.commit()

        schools = s.exec(select(School).where(School.user_id == user.id)).all()

    score = _assess_college_fit(schools)
    # Base: 70, penalty: -10, so around 60
    assert score < 75 and score > 0


def test_application_progress_essays_done():
    """Essays marked as done = progress."""
    user = User(username=_unique_username("test_app"), password_hash="x")
    with db.get_session() as s:
        s.add(user)
        s.commit()
        s.refresh(user)

        # 2 done essays, 1 not done
        s.add(Essay(user_id=user.id, prompt="Test", body="Text", done=True))
        s.add(Essay(user_id=user.id, prompt="Test", body="Text", done=True))
        s.add(Essay(user_id=user.id, prompt="Test", body="Text", done=False))
        s.commit()

        essays = s.exec(select(Essay).where(Essay.user_id == user.id)).all()
        schools = []

    score = _assess_application_progress(schools, essays, [])
    # 2/4 essays = 50% ≈ 33 for essays, others 0, average ≈ 11
    # But let's check the actual calculation
    assert score > 0 and score < 100


def test_financial_readiness_no_schools():
    """No schools entered = 40 (default)."""
    user = User(username=_unique_username("test_fin"), password_hash="x")
    score = _assess_financial_readiness(user, [])
    assert score == 40


def test_financial_readiness_with_costs():
    """Schools with costs entered = points."""
    user = User(username=_unique_username("test_fin_costs"), password_hash="x")
    with db.get_session() as s:
        s.add(user)
        s.commit()
        s.refresh(user)

        # 2 schools with costs
        for i in range(2):
            s.add(
                School(
                    user_id=user.id,
                    name=f"School-{i}",
                    tier=Tier.target,
                    status=AppStatus.not_started,
                    sticker="65000",
                )
            )
        s.commit()

        schools = s.exec(select(School).where(School.user_id == user.id)).all()

    score = _assess_financial_readiness(user, schools)
    # 2 schools * 20pts = 40 + 30 base = 70
    assert score >= 70 and score <= 100


def test_assess_returns_all_fields(test_user):
    """assess() returns complete ReadinessResult with all fields populated."""
    result = assess(test_user)

    assert isinstance(result, ReadinessResult)
    assert 0 <= result.academic <= 100
    assert 0 <= result.extracurricular <= 100
    assert 0 <= result.college_fit <= 100
    assert 0 <= result.application_progress <= 100
    assert 0 <= result.financial_readiness <= 100
    assert 0 <= result.overall <= 100

    # Explanations should be present for all dimensions
    assert "academic" in result.explanations
    assert "extracurricular" in result.explanations
    assert "college_fit" in result.explanations
    assert "application_progress" in result.explanations
    assert "financial_readiness" in result.explanations

    # All explanations should be strings with content
    for key, val in result.explanations.items():
        assert isinstance(val, str)
        assert len(val) > 0

    # Blind spots and next_steps should be lists
    assert isinstance(result.blind_spots, list)
    assert isinstance(result.next_steps, list)


def test_assess_early_stage_student(test_user):
    """Early-stage student (no colleges, no essays, no recs) scores low across board."""
    result = assess(test_user)

    # All should be low
    assert result.college_fit == 0
    assert result.application_progress < 50  # No work done
    assert result.financial_readiness < 50  # No cost research

    # Should have helpful blind spots
    assert len(result.blind_spots) > 0
    assert any("college" in spot["title"].lower() for spot in result.blind_spots)


def test_assess_advanced_student():
    """Advanced student (multiple colleges, essays, recs) scores higher."""
    user_id = None
    with db.get_session() as s:
        user = User(username=_unique_username("advanced"), password_hash="x")
        s.add(user)
        s.commit()
        s.refresh(user)
        user_id = user.id

        # Add 6 schools with good distribution
        for i, tier in enumerate([Tier.safety] * 2 + [Tier.target] * 2 + [Tier.reach] * 2):
            s.add(
                School(
                    user_id=user_id,
                    name=f"School-{i}",
                    tier=tier,
                    status=AppStatus.submitted if i < 3 else AppStatus.not_started,
                    sticker="65000",
                    notes="Visited campus, interested in CS program",
                )
            )

        # Add 2 essays (done)
        s.add(Essay(user_id=user_id, prompt="Common App", body="..." * 50, done=True))
        s.add(Essay(user_id=user_id, prompt="Supplement", body="..." * 40, done=True))

        # Add 2 recommenders
        s.add(Recommender(user_id=user_id, name="Mr. Smith", status="agreed"))
        s.add(Recommender(user_id=user_id, name="Ms. Jones", status="agreed"))

        # Add checkpoints
        for i in range(3):
            s.add(CheckpointProgress(user_id=user_id, checkpoint_key=f"a_test_{i}"))

        s.commit()

    result = assess(user_id)

    # Should score higher
    assert result.college_fit >= 70
    assert result.application_progress > 40
    assert result.financial_readiness >= 50
    assert result.overall > 50


def test_blind_spots_surface_real_gaps():
    """Blind spots should reflect actual missing pieces."""
    user_id = None
    with db.get_session() as s:
        user = User(username=_unique_username("gaps"), password_hash="x")
        s.add(user)
        s.commit()
        s.refresh(user)
        user_id = user.id

        # Add 1 school (incomplete)
        s.add(
            School(
                user_id=user_id,
                name="One School",
                tier=Tier.reach,  # Only reach
                status=AppStatus.not_started,
            )
        )
        s.commit()

    result = assess(user_id)

    # Should detect: not enough schools, no safety, no essays, no recs
    titles = [spot["title"].lower() for spot in result.blind_spots]
    assert any("school" in t for t in titles)  # College fit
    assert any("essay" in t or "application" in t for t in titles)  # Essays


def test_next_steps_are_actionable():
    """Next steps should be specific and ranked."""
    user_id = None
    with db.get_session() as s:
        user = User(username=_unique_username("steps"), password_hash="x")
        s.add(user)
        s.commit()
        s.refresh(user)
        user_id = user.id

        # Minimal setup: 1 school, no essays, no recs
        s.add(School(user_id=user_id, name="Test", tier=Tier.reach))
        s.commit()

    result = assess(user_id)

    # Should have next steps
    assert len(result.next_steps) > 0
    assert all(isinstance(step, str) for step in result.next_steps)

    # Steps should contain an action verb or emoji
    all_steps = " ".join(result.next_steps)
    assert any(word in all_steps.lower() for word in ["research", "write", "ask", "run", "pick"])


def test_scores_bounded_0_to_100():
    """All scores must be 0-100, no negative or >100."""
    user_id = None
    with db.get_session() as s:
        user = User(username=_unique_username("bounded"), password_hash="x")
        s.add(user)
        s.commit()
        s.refresh(user)
        user_id = user.id

        # Add extreme amounts of data
        for i in range(20):
            s.add(TestScore(user_id=user_id, kind="SAT", score="1600"))
        for i in range(20):
            s.add(School(user_id=user_id, name=f"School-{i}", tier=Tier.target))
        for i in range(20):
            s.add(Essay(user_id=user_id, prompt="Test", done=True))
        for i in range(20):
            s.add(Recommender(user_id=user_id, status="agreed"))
        s.commit()

    result = assess(user_id)

    assert 0 <= result.academic <= 100
    assert 0 <= result.extracurricular <= 100
    assert 0 <= result.college_fit <= 100
    assert 0 <= result.application_progress <= 100
    assert 0 <= result.financial_readiness <= 100
    assert 0 <= result.overall <= 100


# ------------------------------------------------- regressions, September 2026
def test_the_best_test_score_counts_not_the_last_one_read():
    """Assigning inside the score loop meant the last row the database handed
    back decided the academic score, so a strong SAT could be wiped out by a
    weak ACT — and, with no ORDER BY, the result was not even stable between
    two calls on the same data."""
    user = User(username=_unique_username("bestscore"), password_hash="x")
    with db.get_session() as s:
        s.add(user); s.commit(); s.refresh(user)
        s.add(TestScore(user_id=user.id, kind="SAT", score="1550"))
        s.add(TestScore(user_id=user.id, kind="ACT", score="20"))
        s.commit()
        rows = s.exec(select(TestScore).where(TestScore.user_id == user.id)).all()

    strong = _assess_academic(user, [r for r in rows if r.kind == "SAT"])
    both = _assess_academic(user, list(rows))
    assert both == strong, "a weak second score dragged the strong one down"
    # And the order it arrives in must not matter.
    assert _assess_academic(user, list(reversed(list(rows)))) == both


def test_an_off_scale_score_is_ignored():
    user = User(username=_unique_username("offscale"), password_hash="x")
    with db.get_session() as s:
        s.add(user); s.commit(); s.refresh(user)
        s.add(TestScore(user_id=user.id, kind="SAT", score="99999"))
        s.commit()
        rows = s.exec(select(TestScore).where(TestScore.user_id == user.id)).all()
    assert _assess_academic(user, list(rows)) == 50  # neutral, not maxed


def test_a_recommender_who_said_yes_counts():
    """The check looked for a status string ("accepted") that this app never
    writes, so a student whose teachers had all agreed was scored as having no
    recommendations at all."""
    from veritagnosis.services.insight import _assess_application_progress
    user = User(username=_unique_username("recsagreed"), password_hash="x")
    with db.get_session() as s:
        s.add(user); s.commit(); s.refresh(user)
        s.add(Recommender(user_id=user.id, name="Mr Smith", status="agreed"))
        s.add(Recommender(user_id=user.id, name="Ms Jones", status="agreed"))
        s.commit()
        recs = s.exec(select(Recommender).where(
            Recommender.user_id == user.id)).all()

    with_agreed = _assess_application_progress([], [], list(recs))
    assert with_agreed > _assess_application_progress([], [], []), \
        "recommenders who agreed contributed nothing"


# ====================================================================
# from test_fit.py
# ====================================================================

def _uid(prefix="fit"):
    with db.get_session() as s:
        u = User(username=f"{prefix}_{uuid.uuid4().hex[:8]}", password_hash="x")
        s.add(u); s.commit(); s.refresh(u)
        return u.id


STRONG = {"gpa": 4.0, "sat": 1580, "act": 36}
MID = {"gpa": 3.6, "sat": 1300, "act": 28}
NONE = {"gpa": None, "sat": None, "act": None}


# ---------------------------------------------------------------- the data
def test_every_college_entry_is_well_formed():
    """A malformed entry would surface as a wrong number on a student's
    screen, so the shape is checked rather than trusted."""
    for c in COLLEGES:
        assert c["name"] and c["state"], c
        assert c["confidence"] in ("high", "medium", "low"), c["name"]
        assert c["source_url"].startswith("http"), c["name"]
        assert c["data_year"], c["name"]
        if c["accept_rate"] is not None:
            assert 0 < c["accept_rate"] <= 100, c["name"]
        # A band must be a band: both ends, in the right order.
        for lo, hi in (("sat_25", "sat_75"), ("act_25", "act_75")):
            a, b = c.get(lo), c.get(hi)
            assert (a is None) == (b is None), f"{c['name']} half a {lo} band"
            if a is not None:
                assert a < b, f"{c['name']} {lo} band is inverted"


def test_uc_campuses_carry_no_test_bands():
    """The UCs are test-blind. Publishing a band for them would imply scores
    matter in a decision where they are not looked at."""
    for c in COLLEGES:
        if c["name"].startswith("UC") or c["name"] == "UCLA":
            assert c["sat_25"] is None and c["act_25"] is None, c["name"]


# ----------------------------------------------------------- the hard rule
def test_a_perfect_student_is_still_a_reach_at_the_most_selective():
    """The single most harmful thing this engine could do is tell someone with
    a 1580 that a 4%-admit college is a safe bet."""
    for name in ("harvard university", "stanford university", "ucla"):
        tier, why = fit.classify(BY_NAME[name], STRONG)
        assert tier == "reach", f"{name} came out {tier} for a perfect score"
        assert "%" in why


def test_nothing_under_twenty_percent_is_ever_a_safety():
    for c in COLLEGES:
        if c["accept_rate"] and c["accept_rate"] < fit.NEVER_SAFE_BELOW:
            for stats in (STRONG, MID, NONE):
                tier, _ = fit.classify(c, stats)
                assert tier != "safety", c["name"]


def test_being_inside_the_band_is_not_treated_as_comfortable():
    """Most applicants inside a selective college's band are still rejected,
    so 'within' must not read as 'you're fine'."""
    tier, why = fit.classify(BY_NAME["university of michigan ann arbor"],
                             {"gpa": 3.9, "sat": 1450, "act": None})
    assert tier == "reach"
    assert "turned down" in why or "most of them" in why


# ------------------------------------------------------- missing data rules
def test_a_college_we_lack_is_reported_as_unknown_not_average():
    sc = School(user_id=1, name="Some College We Do Not Have", tier=Tier.safety)
    f = fit.for_school(sc, STRONG)
    assert f.has_data is False
    assert f.data_tier is None
    assert f.standings == []


def test_no_score_means_no_invented_comparison():
    tier, why = fit.classify(BY_NAME["university of wisconsin-madison"], NONE)
    assert tier is not None
    assert "admit rate alone" in why
    assert fit._standings(BY_NAME["university of wisconsin-madison"], NONE) == []


def test_test_blind_colleges_never_produce_a_score_comparison():
    assert fit._standings(BY_NAME["ucla"], STRONG) == []


# ------------------------------------------------------------- the standing
def test_standing_places_a_value_correctly():
    s = fit.Standing("SAT", 1300, 1360, 1530)
    assert s.place == "below" and "below" in s.sentence
    assert fit.Standing("SAT", 1450, 1360, 1530).place == "within"
    assert fit.Standing("SAT", 1600, 1360, 1530).place == "above"


def test_standing_sentence_names_the_real_numbers():
    s = fit.Standing("ACT", 30, 31, 34)
    assert "30" in s.sentence and "31" in s.sentence and "34" in s.sentence


# ---------------------------------------------------- reading student input
def test_nonsense_scores_are_dropped_not_used():
    """A typo must never place someone above every college in the country."""
    uid = _uid()
    with db.get_session() as s:
        s.add(TestScore(user_id=uid, kind="SAT", score="99999"))
        s.add(TestScore(user_id=uid, kind="ACT", score="not a number"))
        s.commit()
    st = fit.student_stats(uid)
    assert st["sat"] is None and st["act"] is None


def test_the_best_score_of_each_kind_wins():
    uid = _uid()
    with db.get_session() as s:
        s.add(TestScore(user_id=uid, kind="SAT", score="1200"))
        s.add(TestScore(user_id=uid, kind="SAT", score="1400"))
        s.commit()
    assert fit.student_stats(uid)["sat"] == 1400


def test_an_impossible_gpa_is_ignored():
    uid = _uid()
    with db.get_session() as s:
        u = s.get(User, uid); u.gpa = "47"; s.add(u); s.commit()
    assert fit.student_stats(uid)["gpa"] is None


# ------------------------------------------------------------ disagreements
def test_calling_a_reach_a_safety_is_surfaced():
    """The whole point of the screen: catching the expensive mislabel."""
    uid = _uid()
    with db.get_session() as s:
        s.add(School(user_id=uid, name="Harvard University", tier=Tier.safety))
        s.add(TestScore(user_id=uid, kind="SAT", score="1500"))
        s.commit()
    r = fit.review(uid)
    assert len(r["disagreements"]) == 1
    assert r["disagreements"][0].school_name == "Harvard University"


def test_a_correct_label_is_not_flagged():
    uid = _uid()
    with db.get_session() as s:
        s.add(School(user_id=uid, name="Harvard University", tier=Tier.reach))
        s.commit()
    assert fit.review(uid)["disagreements"] == []


def test_a_pessimistic_label_is_not_flagged():
    """Calling a target a reach is cautious, not dangerous — leave it alone."""
    uid = _uid()
    with db.get_session() as s:
        s.add(School(user_id=uid, name="University of Wisconsin-Madison",
                     tier=Tier.reach))
        s.add(TestScore(user_id=uid, kind="SAT", score="1520"))
        s.commit()
    assert fit.review(uid)["disagreements"] == []


# ------------------------------------------------- not blaming the student
def test_the_warnings_are_short_and_actionable():
    """What replaced the data-provenance paragraphs.

    This block used to carry four of them, including one explaining at length
    that a missing safety was "a gap in our data, not a verdict on your list",
    and another reciting how many universities were loaded. Both were written
    for a catalogue of two dozen colleges and both rendered inside a
    statistics box. Every warning is now a single actionable sentence.
    """
    uid = _uid()
    with db.get_session() as s:
        s.add(School(user_id=uid, name="Harvard University", tier=Tier.reach))
        s.commit()
    r = fit.review(uid)
    warnings = r["warnings"]

    # None of the removed prose comes back.
    blob = " ".join(warnings)
    for gone in ("gap in our data", "verdict on your list", "well-known universities",
                 "sharpens every one", "running on admit rates alone",
                 "readiness score use it"):
        assert gone not in blob, f"the old caveat text is back: {gone!r}"

    # And the payload no longer carries a provenance paragraph at all.
    assert "coverage_note" not in r

    # Each remaining warning is one short sentence.
    for w in warnings:
        assert len(w) <= 110, f"too long for a stat box: {w!r}"
        assert w.count(".") <= 1, f"more than one sentence: {w!r}"


def test_a_student_with_no_scores_is_told_to_add_one_briefly():
    uid = _uid()
    with db.get_session() as s:
        s.add(School(user_id=uid, name="Harvard University", tier=Tier.reach))
        s.commit()
    warnings = fit.review(uid)["warnings"]
    assert any("SAT or ACT" in w for w in warnings)
    assert any("GPA" in w for w in warnings)


def test_entering_a_score_removes_its_nudge():
    """Proves the nudge is driven by the student's data, not printed always."""
    uid = _uid()
    with db.get_session() as s:
        s.add(School(user_id=uid, name="Harvard University", tier=Tier.reach))
        s.add(TestScore(user_id=uid, kind="SAT", score="1500"))
        s.commit()
    warnings = " ".join(fit.review(uid)["warnings"])
    assert "SAT or ACT" not in warnings


def test_review_runs_on_an_empty_list():
    r = fit.review(_uid())
    assert r["fits"] == [] and r["disagreements"] == []
    assert r["by_tier"] == {"reach": 0, "target": 0, "safety": 0}


def test_review_reports_missing_colleges_separately():
    uid = _uid()
    with db.get_session() as s:
        s.add(School(user_id=uid, name="Harvard University", tier=Tier.reach))
        s.add(School(user_id=uid, name="Nowhere State", tier=Tier.safety))
        s.commit()
    r = fit.review(uid)
    assert len(r["no_data"]) == 1
    assert r["no_data"][0].school_name == "Nowhere State"


def test_low_confidence_entries_say_so():
    uid = _uid()
    low = next((c for c in COLLEGES if c["confidence"] == "low"), None)
    if low is None:
        pytest.skip("no low-confidence entries loaded")
    with db.get_session() as s:
        s.add(School(user_id=uid, name=low["name"], tier=Tier.target))
        s.commit()
    f = fit.review(uid)["fits"][0]
    assert any("disagree" in c or "rough" in c for c in f.caveats)


def test_every_fit_carries_its_source():
    uid = _uid()
    with db.get_session() as s:
        s.add(School(user_id=uid, name="University of Virginia", tier=Tier.target))
        s.commit()
    f = fit.review(uid)["fits"][0]
    assert f.source_url.startswith("http") and f.data_year


# ------------------------------------------------- entering your own numbers
#
# The engine has read user.gpa and the TestScore rows since it was written.
# There was nowhere in the app to type them, so student_stats() always
# returned {gpa: None, sat: None, act: None} and every comparison ran on
# admit rates alone. These cover the form that fixes that, and — more
# importantly — that what is typed actually changes the answer.

def _profile_state():
    """A ProfileState standing on its own, for the handlers."""
    import types
    from veritagnosis.states.profile_state import ProfileState
    return ProfileState, types.SimpleNamespace()


def test_a_gpa_input_only_accepts_a_number():
    from veritagnosis.states.profile_state import ProfileState
    import types
    f = types.SimpleNamespace(gpa_input="", scores_msg="x")
    ProfileState.set_gpa_input.fn(f, "3.9abc")
    assert f.gpa_input == "3.9"
    ProfileState.set_gpa_input.fn(f, "3.9.4.1")
    assert f.gpa_input.count(".") == 1


def test_score_inputs_strip_anything_that_is_not_a_digit():
    from veritagnosis.states.profile_state import ProfileState
    import types
    f = types.SimpleNamespace(sat_input="", act_input="", scores_msg="")
    ProfileState.set_sat_input.fn(f, "1 4 8 0 pts")
    assert f.sat_input == "1480"
    ProfileState.set_act_input.fn(f, "33!")
    assert f.act_input == "33"


def test_out_of_range_numbers_are_reported_while_typing():
    """A value the parser would drop must not look saved."""
    from veritagnosis.states.profile_state import ProfileState
    import types
    for field, value, expect in [("gpa_input", "9.5", "between 0 and 5"),
                                 ("sat_input", "200", "400 to 1600"),
                                 ("act_input", "99", "1 to 36")]:
        f = types.SimpleNamespace(gpa_input="", sat_input="", act_input="")
        setattr(f, field, value)
        var = {"gpa_input": "gpa_problem", "sat_input": "sat_problem",
               "act_input": "act_problem"}[field]
        msg = getattr(ProfileState, var).fget(f)
        assert expect in msg, f"{field}={value} gave {msg!r}"


def test_a_blank_box_is_not_a_problem():
    from veritagnosis.states.profile_state import ProfileState
    import types
    f = types.SimpleNamespace(gpa_input="", sat_input="", act_input="")
    assert ProfileState.gpa_problem.fget(f) == ""
    assert ProfileState.sat_problem.fget(f) == ""
    assert ProfileState.act_problem.fget(f) == ""


def test_an_entered_sat_changes_the_comparison():
    """The point of the whole form."""
    uid = _uid()
    with db.get_session() as s:
        s.add(School(user_id=uid, name="Harvard University", tier=Tier.reach))
        s.commit()

    before = fit.student_stats(uid)
    assert before["sat"] is None

    with db.get_session() as s:
        s.add(TestScore(user_id=uid, kind="SAT", score="1500"))
        s.commit()

    after = fit.student_stats(uid)
    assert after["sat"] == 1500, "an entered score must reach the engine"

    # and it reaches the comparison, not just the stats dict
    r = fit.review(uid)
    assert not any("SAT or ACT" in w for w in r["warnings"])


def test_an_entered_gpa_changes_the_comparison():
    uid = _uid()
    with db.get_session() as s:
        s.add(School(user_id=uid, name="Harvard University", tier=Tier.reach))
        u = s.get(User, uid)
        u.gpa = "3.91"
        s.add(u)
        s.commit()
    assert fit.student_stats(uid)["gpa"] == 3.91
    assert not any("GPA" in w for w in fit.review(uid)["warnings"])


def test_a_nonsense_stored_score_is_dropped_not_guessed():
    """Belt and braces: the form refuses these, and the engine must too."""
    uid = _uid()
    with db.get_session() as s:
        s.add(TestScore(user_id=uid, kind="SAT", score="99999"))
        s.add(TestScore(user_id=uid, kind="ACT", score="banana"))
        u = s.get(User, uid)
        u.gpa = "not a gpa"
        s.add(u)
        s.commit()
    st = fit.student_stats(uid)
    assert st["sat"] is None and st["act"] is None and st["gpa"] is None
