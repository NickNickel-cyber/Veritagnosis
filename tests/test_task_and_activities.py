"""Today's task follows the real draft, the first sentence earns a checkpoint,
and activities drive the Activities readiness score."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from veritagnosis.models import CheckpointProgress, Essay, School, Tier, User
from veritagnosis.services import activities, apply as progress
from veritagnosis.services import wellbeing as achievements


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'task.db'}",
                           connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _student(s, *schools: str) -> int:
    u = User(username=f"t-{uuid.uuid4().hex[:8]}", password_hash="x")
    s.add(u); s.commit(); s.refresh(u)
    for n in schools:
        s.add(School(user_id=u.id, name=n, tier=Tier.target))
    s.commit()
    return u.id


def _draft(s, uid, body, target=650):
    e = Essay(user_id=uid, prompt="p", body=body, word_target=target)
    s.add(e); s.commit()
    return e


# ------------------------------------------------------------ today's task
def test_an_empty_general_draft_asks_for_a_start(db):
    uid = _student(db, "Rutgers University-New Brunswick")
    _draft(db, uid, "")
    t = progress.next_task(db, uid)
    assert t.title == "Start your essay"
    assert "Blank page" in t.meta


def test_writing_in_the_essay_lab_moves_the_task_on(db):
    """The bug: the Essay Lab's draft has no school attached, so every school
    looked unstarted and the home screen said "Blank page" forever."""
    uid = _student(db, "Rutgers University-New Brunswick", "Carnegie Mellon University")
    _draft(db, uid, "Last spring our robot fell apart an hour before the match. " * 10)
    t = progress.next_task(db, uid)
    assert "Blank page" not in t.meta
    assert t.title == "Keep going on your essay"
    assert t.meta.startswith("110 of 650 words")


def test_a_finished_draft_is_not_sent_back_to_the_essay(db):
    uid = _student(db, "Rutgers University-New Brunswick")
    _draft(db, uid, "word " * 700)
    t = progress.next_task(db, uid)
    assert "essay" not in t.title.lower() or "polish" in t.meta.lower() \
        or "scores" in t.meta.lower()
    assert "Blank page" not in t.meta


def test_a_school_with_its_own_essay_is_named(db):
    uid = _student(db, "Rutgers University-New Brunswick")
    sid = db.exec(select(School).where(School.user_id == uid)).first().id
    e = _draft(db, uid, "")
    e.school_id = sid
    db.add(e); db.commit()
    t = progress.next_task(db, uid)
    assert t.title == "Start your Rutgers University-New Brunswick essay"


# --------------------------------------------------- first-sentence checkpoint
def test_a_full_sentence_is_counted_and_half_a_thought_is_not():
    assert achievements.full_sentences("") == 0
    assert achievements.full_sentences("Hi.") == 0
    assert achievements.full_sentences("Last spring our robot") == 0
    assert achievements.full_sentences("Last spring our robot fell apart.") == 1


def test_the_first_sentence_earns_a_checkpoint(db):
    uid = _student(db)
    _draft(db, uid, "Last spring our robot fell apart.")
    new = achievements.award(db, uid)
    assert "a_first_sentence" in {a["key"] for a in new}
    # Once only.
    assert "a_first_sentence" not in {a["key"] for a in achievements.award(db, uid)}
    keys = {r.checkpoint_key for r in db.exec(
        select(CheckpointProgress).where(CheckpointProgress.user_id == uid)).all()}
    assert "a_first_sentence" in keys


def test_the_essay_screen_checks_the_moment_a_sentence_ends():
    from veritagnosis.states.apply_state import EssayState

    class Probe:
        _WORD_MARKS = EssayState._WORD_MARKS
        _writing_mark = "0:0"
        _mark_for = EssayState._mark_for
        _crossed_mark = EssayState._crossed_mark

    p = Probe()
    assert not p._crossed_mark("Last spring our robot")
    assert p._crossed_mark("Last spring our robot fell apart.")


# ------------------------------------------------------------- activities
CAPTAIN = {"name": "Varsity soccer captain", "intensity": "intense",
           "years": "3", "leadership": "no"}
CLUB = {"name": "Robotics club", "intensity": "moderate", "years": "2",
        "leadership": "no"}


def test_no_activities_is_zero():
    assert activities.score([]) == 0


def test_leadership_words_count_like_the_star():
    starred = {**CLUB, "leadership": "yes"}
    named = {**CLUB, "name": "Robotics club president"}
    plain = activities.score_one(CLUB).points
    assert activities.score_one(starred).points == plain + activities.LEADERSHIP_POINTS
    assert activities.score_one(named).points == plain + activities.LEADERSHIP_POINTS


def test_clubs_and_teams_count_and_say_so():
    sc = activities.score_one(CLUB)
    assert any("Robotics" in x or "club" in x for x in sc.signals)
    bare = activities.score_one({**CLUB, "name": "Robots"})
    assert sc.points > bare.points


def test_intensive_work_counts_more_than_light():
    light = activities.score_one({"name": "Piano", "intensity": "light", "years": "1"})
    intense = activities.score_one({"name": "Piano", "intensity": "intense", "years": "1"})
    named = activities.score_one({"name": "Intensive piano program", "intensity": "light",
                                  "years": "1"})
    assert intense.points > light.points
    assert named.points > light.points


def test_low_commitment_words_take_points_off():
    a = activities.score_one({"name": "Guitar", "intensity": "moderate", "years": "1"})
    b = activities.score_one({"name": "Guitar sometimes for fun", "intensity": "moderate",
                              "years": "1"})
    assert b.points < a.points


def test_years_add_up_to_a_cap():
    one = activities.score_one({**CLUB, "years": "1"}).points
    four = activities.score_one({**CLUB, "years": "4"}).points
    six = activities.score_one({**CLUB, "years": "6"}).points
    assert one < four <= six


def test_depth_beats_breadth():
    deep = [CAPTAIN, {**CLUB, "leadership": "yes", "years": "3"}]
    thin = [{"name": f"Activity {i}", "intensity": "light", "years": "1"}
            for i in range(8)]
    assert activities.score(deep) > activities.score(thin)
    assert activities.spread_thin([activities.score_one(r) for r in thin])
    assert "spread thin" in activities.explain(thin)


def test_scores_stay_between_0_and_100():
    huge = [{"name": "Founder and president of the robotics team, state champion",
             "intensity": "intense", "years": "6", "leadership": "yes"}] * 30
    assert activities.score(huge) == 100
    bad = [{"name": "watching tv casually", "intensity": "light", "years": "1"}]
    assert activities.score(bad) == 0


def test_bad_profile_data_never_raises():
    for raw in (None, "", "not json", "[]", '{"extracurriculars": "x"}',
                '{"extracurriculars": [1, null, {"name": ""}]}'):
        assert activities.parse(raw) == []


def test_the_readiness_engine_uses_them():
    from veritagnosis.services.insight import _assess_extracurricular, _explain_extracurricular
    u = User(username="x", password_hash="x",
             profile_data=json.dumps({"extracurriculars": [CAPTAIN, CLUB]}))
    assert _assess_extracurricular(u, [], []) == activities.score([CAPTAIN, CLUB])
    assert "Varsity soccer captain" in _explain_extracurricular(u, [], [])
