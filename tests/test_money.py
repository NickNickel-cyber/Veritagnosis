"""
Paying for it: the Student Aid Index model, Pell, pricing the student's
own college list, the FAFSA calendar, and the aid checklist.

Merged from: test_fafsa, test_aid_and_breaks.
"""
from __future__ import annotations

import pytest
from veritagnosis.services import money as fafsa
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel import select as _select
from veritagnosis.content import aid as content
from veritagnosis.models import CalmLog, School, Scholarship, Tier, User, utcnow
from veritagnosis import security as auth
from veritagnosis.services import money as aid, wellbeing as breaks


# ====================================================================
# from test_fafsa.py
# ====================================================================

def test_the_pell_figures_are_the_2026_27_published_ones():
    """Dear Colleague Letter GEN-26-01, US Department of Education."""
    assert fafsa.PELL_MAX == 7395
    assert fafsa.PELL_MIN == 740
    assert fafsa.PELL_MIN == round(fafsa.PELL_MAX * 0.10 / 5) * 5
    # The cut-off is twice the maximum, set by the One Big Beautiful Bill Act.
    assert fafsa.PELL_SAI_CUTOFF == 2 * fafsa.PELL_MAX == 14790


@pytest.mark.parametrize("size,expected", [
    (1, 15650), (2, 21150), (3, 26650), (4, 32150),
    (5, 37650), (6, 43150), (7, 48650), (8, 54150),
])
def test_the_poverty_guideline_matches_hhs_2025(size, expected):
    assert fafsa.poverty_line(size) == expected


def test_the_pell_thresholds_are_the_right_way_round():
    """A single-parent household gets the more generous line, and the minimum
    line always sits above the maximum line."""
    for kind in ("single", "two"):
        assert fafsa.MIN_PELL_FPL[kind] > fafsa.MAX_PELL_FPL[kind]
    assert fafsa.MAX_PELL_FPL["single"] > fafsa.MAX_PELL_FPL["two"]


# -------------------------------------------------------------- Pell routing
def test_a_low_income_household_gets_the_maximum_pell_whatever_the_sai():
    """Under 1.75x the poverty line the maximum is automatic. This is the rule
    that stops a family with some savings being written out of Pell."""
    h = fafsa.Household(income=30_000, household=4, parent_savings=90_000)
    r = fafsa.student_aid_index(h)
    assert r.pell == fafsa.PELL_MAX
    assert "poverty line" in r.pell_basis


def test_a_high_income_household_gets_no_pell():
    r = fafsa.student_aid_index(fafsa.Household(income=250_000, household=4))
    assert r.pell == 0
    assert r.sai >= fafsa.PELL_SAI_CUTOFF


def test_pell_never_lands_between_zero_and_the_minimum():
    """An award below the statutory minimum is not paid at all, so no income
    should ever produce, say, $300 of Pell."""
    for income in range(0, 200_001, 2_500):
        pell = fafsa.student_aid_index(fafsa.Household(income=income)).pell
        assert pell == 0 or pell >= fafsa.PELL_MIN


def test_pell_never_exceeds_the_maximum():
    for income in range(0, 200_001, 5_000):
        assert fafsa.student_aid_index(
            fafsa.Household(income=income)).pell <= fafsa.PELL_MAX


# ------------------------------------------------------------ the lessons
def test_income_moves_the_number_far_more_than_savings():
    """The single most common wrong belief is that savings are what cost you
    aid. If this ever inverts, the screen is teaching the opposite of the
    truth."""
    base = fafsa.Household(income=70_000, parent_savings=10_000)
    more_income = fafsa.student_aid_index(
        fafsa.Household(income=80_000, parent_savings=10_000)).sai
    more_savings = fafsa.student_aid_index(
        fafsa.Household(income=70_000, parent_savings=20_000)).sai
    start = fafsa.student_aid_index(base).sai

    assert (more_income - start) > (more_savings - start) * 3


def test_the_first_ten_thousand_of_savings_costs_nothing():
    a = fafsa.student_aid_index(fafsa.Household(parent_savings=0)).sai
    b = fafsa.student_aid_index(
        fafsa.Household(parent_savings=fafsa.ASSET_PROTECTION)).sai
    assert a == b


def test_a_students_own_savings_are_assessed_harder_than_a_parents():
    """20% against 12%, which is the reason to keep money in a parent's name
    and a thing families are rarely told."""
    parent = fafsa.student_aid_index(fafsa.Household(
        parent_savings=fafsa.ASSET_PROTECTION + 10_000, student_savings=0)).sai
    student = fafsa.student_aid_index(fafsa.Household(
        parent_savings=fafsa.ASSET_PROTECTION, student_savings=10_000)).sai
    assert student > parent


def test_the_sai_never_falls_below_the_floor():
    r = fafsa.student_aid_index(fafsa.Household(
        income=0, parent_savings=0, student_income=0, student_savings=0))
    assert r.sai >= fafsa.SAI_FLOOR


def test_a_raise_never_costs_more_than_it_gains():
    """Progressive bands, so crossing one must never leave a family worse off
    in absolute terms. Families genuinely fear this and turn down hours over
    it."""
    for income in range(20_000, 200_000, 5_000):
        a = fafsa.student_aid_index(fafsa.Household(income=income)).sai
        b = fafsa.student_aid_index(fafsa.Household(income=income + 5_000)).sai
        assert (b - a) < 5_000


# --------------------------------------------------------------- colleges
def test_the_dearest_college_can_be_the_cheapest_one_to_attend():
    """The whole reason the screen exists. A college that meets full need at
    an $85,000 sticker should beat a $29,000 one that meets 60%, for a family
    with real need."""
    r = fafsa.student_aid_index(fafsa.Household(income=45_000))
    rows = fafsa.what_you_would_pay(r)
    cheapest = rows[0]
    assert cheapest.cost == max(x.cost for x in rows)
    assert cheapest.meets == 100


def test_a_wealthy_family_pays_the_sticker_price_everywhere():
    """With no demonstrated need, "meets 100% of need" is worth nothing, and
    the ranking should collapse back to sticker order."""
    r = fafsa.student_aid_index(fafsa.Household(income=400_000))
    rows = fafsa.what_you_would_pay(r)
    assert rows[0].cost == min(x.cost for x in rows)
    for e in rows:
        assert e.you_pay <= e.cost


def test_nobody_is_ever_asked_for_more_than_the_sticker_price():
    for income in range(0, 400_001, 10_000):
        r = fafsa.student_aid_index(fafsa.Household(income=income))
        for e in fafsa.what_you_would_pay(r):
            assert 0 <= e.you_pay <= e.cost


# ------------------------------------------------------------ experiments
def test_moving_savings_into_retirement_lowers_the_sai():
    """Because FAFSA cannot see a retirement account. Same money, different
    pot, and it stops counting."""
    h = fafsa.Household(income=90_000, parent_savings=60_000)
    before = fafsa.student_aid_index(h).sai
    after = fafsa.student_aid_index(fafsa.apply_experiment(h, "retire")).sai
    assert after < before


def test_a_second_sibling_in_college_does_not_cut_the_contribution():
    """It did before 2024. Families plan around the old rule and are caught
    out, so this must not quietly start behaving like the old one."""
    h = fafsa.Household(income=90_000, household=4, in_college=1)
    before = fafsa.student_aid_index(h).sai
    after = fafsa.student_aid_index(fafsa.apply_experiment(h, "sibling")).sai
    assert after >= before * 0.75


def test_every_experiment_is_runnable_and_changes_something_or_nothing_safely():
    h = fafsa.Household()
    for x in fafsa.EXPERIMENTS:
        out = fafsa.apply_experiment(h, x.key)
        assert isinstance(out, fafsa.Household)
        r = fafsa.student_aid_index(out)
        assert r.sai >= fafsa.SAI_FLOOR
    # An unknown key must be inert rather than an error.
    assert fafsa.apply_experiment(h, "nonsense") == h


def test_the_parts_add_up_to_the_total():
    h = fafsa.Household(income=95_000, parent_savings=40_000,
                        student_income=14_000, student_savings=6_000)
    r = fafsa.student_aid_index(h)
    parts = (r.parent_income_part + r.parent_asset_part
             + r.student_income_part + r.student_asset_part)
    assert abs(parts - r.sai) <= 2      # rounding only


# ===================================================================
# Pricing the student's own list
# ===================================================================
class _Sc:
    def __init__(self, name): self.name = name


def _result(income=65000, household=4, savings=25000):
    return fafsa.student_aid_index(fafsa.Household(
        income=income, household=household, parent_savings=savings,
        student_income=4000, student_savings=1500))


def test_a_college_we_have_no_cost_for_is_reported_not_guessed():
    rows = fafsa.price_your_list(_result(), [_Sc("Nowhere State")])
    assert len(rows) == 1
    assert rows[0].has_cost is False
    assert rows[0].cost == 0 and rows[0].pay_if_generous == 0


def test_need_is_cost_minus_sai():
    r = _result()
    row = fafsa.price_your_list(r, [_Sc("University of Wisconsin-Madison")])[0]
    assert row.need == row.cost - r.sai


def test_a_generous_expensive_college_can_beat_a_cheap_stingy_one():
    """The central lesson of the whole screen. If this stops being true the
    simulator has stopped teaching the thing it exists to teach."""
    r = _result(income=45000)
    rows = {e.name: e for e in fafsa.price_your_list(
        r, [_Sc("Harvard University"), _Sc("University of Wisconsin-Madison")])}
    dear, cheap = rows["Harvard University"], rows["University of Wisconsin-Madison"]
    assert dear.cost > cheap.cost
    assert dear.pay_if_generous <= cheap.pay_if_typical


def test_the_range_is_ordered_and_never_negative():
    r = _result()
    for e in fafsa.price_your_list(r, [_Sc("Harvard University"),
                                       _Sc("University of Virginia")]):
        assert e.pay_if_generous <= e.pay_if_typical
        assert e.pay_if_generous >= 0 and e.pay_if_typical >= 0
        assert e.pay_if_typical <= e.cost


def test_pell_never_exceeds_the_need_that_exists():
    r = _result(income=20000)
    for e in fafsa.price_your_list(r, [_Sc("University of Wisconsin-Madison")]):
        assert e.pell <= e.need


def test_every_priced_college_carries_its_source():
    e = fafsa.price_your_list(_result(), [_Sc("University of Michigan Ann Arbor")])[0]
    assert e.source_url.startswith("http") and e.data_year and e.confidence


def test_colleges_without_data_sort_last():
    rows = fafsa.price_your_list(_result(), [
        _Sc("Nowhere State"), _Sc("Harvard University")])
    assert rows[0].has_cost is True
    assert rows[-1].has_cost is False


def test_pricing_an_empty_list_is_not_an_error():
    assert fafsa.price_your_list(_result(), []) == []


# ===================================================================
# The calendar
# ===================================================================
def test_the_timeline_knows_each_phase_of_the_year():
    import datetime as dt
    phases = {
        dt.date(2026, 9, 16): "before_open",   # a fortnight out
        dt.date(2026, 10, 15): "open_early",   # just opened
        dt.date(2027, 2, 1): "open_late",      # state money going
        dt.date(2027, 7, 1): "closing",        # late, still worth it
    }
    for day, expected in phases.items():
        assert fafsa.timeline(day).phase == expected, day


def test_filing_late_is_never_framed_as_pointless():
    """A student who has already missed the good window must not be told they
    have blown it — federal aid is not first-come, and despair here costs them
    money."""
    import datetime as dt
    t = fafsa.timeline(dt.date(2027, 7, 1))
    assert "still worth" in t.detail or "better than never" in t.headline
    assert "Pell" in t.detail


def test_the_award_year_is_well_formed_all_year_round():
    import datetime as dt
    for month in range(1, 13):
        t = fafsa.timeline(dt.date(2027, month, 14))
        assert len(t.award_year) == 7 and t.award_year[4] == "-", t.award_year


# ====================================================================
# from test_aid_and_breaks.py
# ====================================================================

@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def uid(db):
    return auth.register(db, "nick", "Str0ng-Pass!42",
                     email="nick@example.com").id


# ------------------------------------------------------------------- money
@pytest.mark.parametrize("text,expected", [
    ("$32,000", 32000.0), ("32000", 32000.0), ("32k", 32000.0),
    ("  45,500  ", 45500.0), ("$0", 0.0), ("0", 0.0),
    ("about 12,300.50", 12300.5), ("$1.2k", 1200.0),
])
def test_money_reads_what_people_actually_type(text, expected):
    assert aid.money(text) == expected


@pytest.mark.parametrize("junk", ["", "   ", None, "n/a", "ask mum", "$"])
def test_money_refuses_to_guess(junk):
    """None, not 0. Zero is a real answer — "this would cost me nothing" — and
    confusing it with "we could not read this" would show a family a free
    college."""
    assert aid.money(junk) is None


def test_zero_is_kept_distinct_from_unknown():
    assert aid.money("0") == 0.0
    assert aid.money("") is None
    assert aid.fmt(0.0) == "$0"
    assert aid.fmt(None) == "—"


# -------------------------------------------------------------------- cost
def _school(db, uid, **kw):
    s = School(user_id=uid, name=kw.pop("name", "NYU"), **kw)
    db.add(s); db.commit(); db.refresh(s)
    return s


def test_net_cost_is_sticker_minus_aid(db, uid):
    s = _school(db, uid, sticker="$70,000", aid_offered="$38,000")
    assert aid.school_cost(s).net == 32000.0


def test_a_typed_net_price_beats_the_subtraction(db, uid):
    """It came off a real offer letter or a net price calculator, and both are
    better than our arithmetic."""
    s = _school(db, uid, sticker="$70,000", aid_offered="$38,000",
                net_cost="$29,500")
    assert aid.school_cost(s).net == 29500.0


def test_aid_larger_than_sticker_never_goes_negative(db, uid):
    s = _school(db, uid, sticker="$20,000", aid_offered="$26,000")
    assert aid.school_cost(s).net == 0.0


def test_a_school_with_no_numbers_is_not_pretended_to_be_free(db, uid):
    s = _school(db, uid)
    c = aid.school_cost(s)
    assert c.net is None and c.known is False


def test_costs_are_sorted_cheapest_known_first(db, uid):
    _school(db, uid, name="Dear", sticker="$70,000")
    _school(db, uid, name="Cheap", sticker="$12,000")
    _school(db, uid, name="Unknown")
    order = [c.name for c in aid.costs(db, uid)]
    assert order[:2] == ["Cheap", "Dear"]
    assert order[-1] == "Unknown"


# ------------------------------------------------------------------- flags
def test_two_binding_applications_are_flagged(db, uid):
    """ED is a commitment to attend. Holding two is a real problem, not a
    preference, and the screen has to say so."""
    _school(db, uid, name="A", round="ed")
    _school(db, uid, name="B", round="ed2")
    cs = aid.costs(db, uid)
    warns = [f for f in aid.flags(db, uid, cs) if f.level == "warn"]
    assert any("binding" in f.title.lower() for f in warns)


def test_one_binding_application_is_explained_not_warned_about(db, uid):
    _school(db, uid, name="A", round="ed")
    fl = aid.flags(db, uid, aid.costs(db, uid))
    binding = [f for f in fl if "binding" in f.title.lower()]
    assert binding and binding[0].level == "info"


def test_a_close_aid_deadline_is_flagged(db, uid):
    from datetime import timedelta
    _school(db, uid, name="Soon", aid_deadline=utcnow() + timedelta(days=5))
    fl = aid.flags(db, uid, aid.costs(db, uid))
    assert any(f.level == "warn" and "close" in f.title.lower() for f in fl)


def test_no_costs_recorded_says_so_once_and_helpfully(db, uid):
    _school(db, uid, name="A")
    fl = aid.flags(db, uid, aid.costs(db, uid))
    assert any("net price calculator" in f.detail for f in fl)


# --------------------------------------------------------------- checklist
def test_a_step_can_be_ticked_and_unticked(db, uid):
    """Someone will tap the wrong row, and a checklist you cannot correct is a
    checklist people stop trusting."""
    key = content.STEPS[0]["key"]
    assert aid.toggle(db, uid, key) is True
    assert aid.done_keys(db, uid) == {key}
    assert aid.toggle(db, uid, key) is False
    assert aid.done_keys(db, uid) == set()


def test_an_unknown_step_key_is_ignored(db, uid):
    assert aid.toggle(db, uid, "not-a-real-step") is False
    assert aid.done_keys(db, uid) == set()


def test_checklist_percent_spans_zero_to_one_hundred(db, uid):
    assert aid.checklist_percent(set()) == 0
    every = {s["key"] for s in content.STEPS}
    assert aid.checklist_percent(every) == 100


def test_every_step_key_is_unique():
    keys = [s["key"] for s in content.STEPS]
    assert len(keys) == len(set(keys))


def test_every_step_belongs_to_a_declared_phase():
    """A step in an unlisted phase would simply never render."""
    for s in content.STEPS:
        assert s["phase"] in content.PHASES, s["key"]


def test_the_disclaimer_actually_disclaims():
    d = content.DISCLAIMER.lower()
    assert "not financial advice" in d or "isn't financial advice" in d
    assert "counsellor" in d or "counselor" in d


# ---------------------------------------------------------------- summary
def test_summary_survives_an_empty_list(db, uid):
    s = aid.summary(db, uid)
    assert s["priced"] == 0 and s["cheapest"] == ""


def test_summary_counts_won_scholarship_money(db, uid):
    db.add(Scholarship(user_id=uid, name="Rotary", amount="$2,500", status="won"))
    db.add(Scholarship(user_id=uid, name="Local", amount="$1,000", status="found"))
    db.commit()
    s = aid.summary(db, uid)
    assert s["won"] == "$2,500"
    assert s["chasing"] == "$1,000"


# ------------------------------------------------------------------ breaks
def test_a_break_is_logged_and_paid_per_minute(db, uid):
    before = db.get(User, uid).xp
    gained = breaks.log(db, uid, "graze", 15, score=4200)
    assert gained == 15 * breaks.XP_PER_MINUTE
    assert db.get(User, uid).xp == before + gained
    rows = db.exec(_select(CalmLog)).all()
    assert len(rows) == 1 and rows[0].minutes == 15


def test_xp_is_capped_so_a_long_session_cannot_be_farmed(db, uid):
    assert breaks.log(db, uid, "graze", 60) == breaks.XP_CAP


def test_a_high_score_pays_no_more_than_a_low_one(db, uid):
    """Paying by score would turn a stress screen into a grind, which is the
    exact opposite of what it is for."""
    a = breaks.log(db, uid, "graze", 15, score=10)
    b = breaks.log(db, uid, "graze", 15, score=999999)
    assert a == b


def test_a_zero_length_session_pays_nothing_and_logs_nothing(db, uid):
    assert breaks.log(db, uid, "graze", 0) == 0
    assert db.exec(_select(CalmLog)).all() == []


def test_break_minutes_are_clamped(db, uid):
    """The length reaching this function must never be able to mint XP, however
    it got here."""
    breaks.log(db, uid, "graze", 99999)
    assert db.exec(_select(CalmLog)).all()[0].minutes <= 60


def test_break_stats_are_per_kind(db, uid):
    """Graze is the only screen writing breaks today, but the kind filter is
    what keeps a second one from silently merging into its totals — so it is
    tested with two kinds even though only one is currently in use."""
    breaks.log(db, uid, "graze", 15, score=900)
    breaks.log(db, uid, "other", 2, score=40)
    assert breaks.stats(db, uid, "other")["sessions"] == 1
    assert breaks.stats(db, uid, "other")["minutes"] == 2
    assert breaks.stats(db, uid, "graze")["minutes"] == 15
    assert breaks.stats(db, uid)["sessions"] == 2


def test_breaks_never_touch_the_meditation_streak(db, uid):
    """Several checkpoints count consecutive days of breathing. Counting a game
    session as a sitting would tell someone they had meditated for a week when
    they had not."""
    from veritagnosis.models import MeditationLog
    breaks.log(db, uid, "graze", 20)
    assert db.exec(_select(MeditationLog)).all() == []


# ------------------------------------------------------------ game content
def test_the_game_dresses_every_theme():
    from veritagnosis.ui import widgets as graze
    from veritagnosis.states.base import THEME_KEYS
    for key in THEME_KEYS:
        assert key in graze.THEMES, f"{key} has no costume"
        look = graze.THEMES[key]
        assert set(look["sides"]) == set(graze.KINDS)
        assert set(look["words"]) == set(graze.KINDS)


def test_game_upgrades_have_unique_ids_and_real_prerequisites():
    from veritagnosis.ui import widgets as graze
    ids = [u["id"] for u in graze.UPGRADES]
    assert len(ids) == len(set(ids))
    for u in graze.UPGRADES:
        if u.get("need"):
            assert u["need"] in ids, f"{u['id']} needs a nonexistent upgrade"


def test_session_lengths_are_the_ones_that_were_asked_for():
    from veritagnosis.ui import widgets as graze
    assert graze.LENGTHS == [15, 20]
