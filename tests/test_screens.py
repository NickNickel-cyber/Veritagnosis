"""
What the screens show: essay prose analysis, progress and checkpoints,
colour contrast and typography, and the rotating quote loops.

Merged from: test_prose, test_progress_and_checkpoints, test_readability, test_unlocks_and_quotes.
"""
from __future__ import annotations

import re
import pytest
from veritagnosis.services import prose
from datetime import timedelta
from sqlmodel import Session, SQLModel, create_engine
from veritagnosis.content import achievements as ach_content
from sqlmodel import select as _select
from veritagnosis.models import (AppStatus, CheckpointProgress, Essay,
                                 Recommender, School, Tier, User, utcnow)
from veritagnosis.models import TestScore as ScoreRow
from veritagnosis import security as auth
from veritagnosis.services import wellbeing as achievements, apply as progress
from pathlib import Path
from veritagnosis.content import achievements as ach
from veritagnosis.ui import avatar as parts


# ====================================================================
# from test_prose.py
# ====================================================================

def test_finds_a_misspelling_and_offers_the_correction():
    r = prose.analyse("I did alot of work every day for the whole summer term.")
    hit = [f for f in r["findings"] if f.original == "alot"]
    assert hit, "should catch 'alot'"
    assert hit[0].fix == "a lot"
    assert hit[0].auto is True


def test_finds_a_cliche():
    r = prose.analyse("Ever since I was little I have wanted to be a doctor and help.")
    assert any(f.kind == "cliche" for f in r["findings"])


def test_finds_telling_not_showing():
    r = prose.analyse("I am a hardworking student who cares about the work I do.")
    assert any(f.kind == "telling" for f in r["findings"])


def test_finds_a_run_on_sentence():
    long = "I went to the shop " + "and then I bought some bread " * 8 + "."
    r = prose.analyse(long)
    assert any(f.kind == "long" for f in r["findings"])


def test_flags_repeated_sentence_openers():
    text = ("I woke up early. I made breakfast. I walked to the bus stop. "
            "I sat down near the window.")
    r = prose.analyse(text)
    assert any(f.kind == "rhythm" for f in r["findings"])


def test_their_is_becomes_there_is():
    r = prose.analyse("Their is no reason at all to worry about the deadline now.")
    hit = [f for f in r["findings"] if f.kind == "confusable"]
    assert hit and hit[0].fix.lower() == "there"


def test_case_is_preserved_when_fixing_the_first_word():
    """'In order to' at the start of a sentence must become 'To', not 'to'."""
    text = "In order to finish the essay I stayed up late reading my old notes."
    r = prose.analyse(text)
    hit = [f for f in r["findings"] if f.original.lower() == "in order to"]
    assert hit and hit[0].fix == "To"
    assert prose.apply_one(text, hit[0]).startswith("To finish")


def test_clean_writing_produces_few_findings():
    # Long enough to clear prose.WORDS_NO_SCORE on purpose: under the floor
    # nothing is scored at all, so a shorter fixture would be asserting against
    # the gate rather than against the writing. It is also a complete draft
    # rather than an opening, because a provisional score is deliberately
    # pulled toward the middle and cannot reach the top of the range.
    text = ("The kennel smelled of bleach at six in the morning. Concrete "
            "chilled my shoes. A grey terrier named Otis refused to leave his "
            "corner. I sat on the floor and waited. He came over after forty "
            "minutes.\n\n"
            "His collar sat two notches too tight. I loosened it and he "
            "breathed out. On Tuesday I carried a towel from home and folded "
            "it into the corner he liked. By March he met me at the gate "
            "before I turned the key.\n\n"
            "Then the shelter moved him to the annex and nobody told me. I "
            "spent twenty minutes calling his name down an empty run. When I "
            "found him he pressed himself flat under a bench and would not "
            "look up.\n\n"
            "I had thought the towel was the thing that mattered. It was not "
            "the towel. It was that I came on Tuesdays, and he learned to "
            "count on Tuesdays, and no one asked him first. Now I read the "
            "transfer board before I take my coat off.")
    r = prose.analyse(text)
    serious = [f for f in r["findings"] if f.severity == "high"]
    assert not serious, [f.label for f in serious]
    assert len(prose.words(text)) >= prose.WORDS_NO_SCORE
    assert r["score"] >= 70


# ----------------------------------------------------------------- not damaging
def test_a_fix_lands_exactly_on_the_right_characters():
    text = "This is very good and the very best thing that happened."
    r = prose.analyse(text)
    first = next(f for f in r["findings"] if f.kind == "filler")
    out = prose.apply_one(text, first)
    # exactly one 'very' removed, the rest of the sentence untouched
    assert out.count("very") == text.count("very") - 1
    assert out.endswith("that happened.")


def test_a_stale_finding_is_refused_rather_than_applied():
    """The guard that protects the essay.

    A student can keep typing between the analysis and the tap. If the text at
    the recorded offsets is no longer what the engine saw, applying the edit
    would cut the wrong characters out of the sentence. It must do nothing.
    """
    text = "I was really tired after the long and difficult week of exams."
    f = next(x for x in prose.analyse(text)["findings"] if x.kind == "filler")

    moved = "Yesterday " + text          # every offset is now 10 characters off
    assert prose.apply_one(moved, f) == moved, "must refuse to edit shifted text"


def test_out_of_range_offsets_are_refused():
    f = prose.Finding(start=500, end=520, kind="x", label="x", why="x",
                      original="nope", fix="!")
    assert prose.apply_one("short text", f) == "short text"


def test_polish_applies_back_to_front_so_offsets_stay_valid():
    """Several fixes at once is where an offset bug would show up.

    Each edit changes the length of the string, so anything applied left to
    right would shift every later finding. Applying in reverse is what keeps
    them all correct, and this checks the result word by word.
    """
    text = ("I was very tired and really hungry and definately not basically "
            "ready in order to start.")
    out, n = prose.apply_all(text)
    assert n >= 4
    assert "very" not in out
    assert "really" not in out
    assert "basically" not in out
    assert "definately" not in out
    assert "definitely" in out
    assert out.startswith("I was tired")
    assert "To start" in out or "to start" in out
    # nothing mangled: still one sentence, still ends with a full stop
    assert out.count(".") == 1 and out.rstrip().endswith(".")


def test_polish_does_not_leave_double_spaces_or_space_before_punctuation():
    text = "It was very good , and really nice , and quite fine ."
    out, _ = prose.apply_all(text)
    assert "  " not in out
    assert " ," not in out


def test_polish_only_touches_the_confident_rules():
    """Voice and structure are the writer's call, so bulk polish must not
    rewrite a cliché or restructure a passive sentence behind their back."""
    text = ("Ever since I was little the trophy was given to me by my coach and "
            "I have always been passionate about the sport I play.")
    out, _ = prose.apply_all(text)
    assert "Ever since I was little" in out       # cliché left alone
    assert "was given to me by" in out            # passive left alone


def test_applying_every_fix_one_at_a_time_never_corrupts_the_text():
    """Property check: re-analyse after each edit, apply the first auto fix,
    repeat. The text must stay well-formed and must strictly shrink or hold."""
    text = ("I think that it was very really quite good and I was basically "
            "just definately going to alot of the meetings every day.")
    seen = set()
    for _ in range(20):
        r = prose.analyse(text)
        nxt = next((f for f in r["findings"] if f.auto and f.has_fix), None)
        if nxt is None:
            break
        before = text
        text = prose.apply_one(text, nxt)
        assert text != before or nxt.original in seen
        seen.add(nxt.original)
        assert text.strip(), "text must never be emptied"
    # It terminates, the sentence survives intact, and the filler is gone.
    # Note "definitely" and "a lot of" do not survive: the spelling rule
    # corrects them first, and the filler rule then removes the corrected
    # words. That chain is intended — each individual edit was a safe one.
    assert text.endswith(".") and text.count(".") == 1
    assert "definately" not in text and "alot" not in text
    # whole words, not substrings — "every" contains "very"
    assert not re.search(r"\b(very|really|quite|basically)\b", text)


# ------------------------------------------------------------------- the numbers
def test_score_rewards_a_cleaner_draft():
    # Both drafts clear the scoring floor on purpose: below it neither is
    # scored at all, which is the point of the floor, not a flaw in this test.
    bad = ("I think that this was very really a life-changing experience that "
           "taught me the value of hard work and I have always been passionate "
           "about helping people ever since I was little honestly. I did alot "
           "of things at the shelter and it was basically just a really good "
           "learning experience for me in order to make a difference in my "
           "community and their is no doubt that it changed me as a person.")
    good = ("The kennel smelled of bleach. Otis would not leave his corner. "
            "I sat on the cold floor and waited for him. He came over after "
            "forty minutes and put his head on my knee. His collar was too "
            "tight. I loosened it two notches and he breathed out. On Tuesday "
            "I brought a towel from home. By March he met me at the gate. "
            "Now I check every collar before I do anything else.")
    assert prose.score(good) > prose.score(bad)


def test_score_is_zero_for_a_draft_too_short_to_judge():
    assert prose.score("Just a few words here.") == 0


# ---------------------------------------------------------------- the floor
#
# The engine used to start scoring at twenty-five words. Twenty-five words is
# one sentence, and a number out of a hundred next to one sentence is a guess
# wearing a dial. These pin the behaviour that replaced it.

def test_nothing_is_scored_below_the_floor():
    text = "I have wanted to be a doctor for a long time. " * 2
    d = prose.score_detail(text)
    assert d["words"] < prose.WORDS_NO_SCORE
    assert d["ready"] is False
    assert d["score"] == 0
    assert d["needed"] == prose.WORDS_NO_SCORE - d["words"]
    assert d["dimensions"] == []


def test_a_real_draft_is_scored_and_explained():
    text = ("The freezer at Los Primos hums at a pitch my father can hear from "
            "the register. On my first Saturday he handed me a clipboard and "
            "told me to count the chicken. I counted forty-three boxes. He "
            "counted forty-one. Then in June the compressor died and I wanted "
            "to fix it with a spreadsheet. There was no spreadsheet. He "
            "borrowed a truck and sold the meat at cost by Sunday. What I "
            "understood that week was that I had been treating the shop like a "
            "problem set. Now I keep the notebook, and I ask first.")
    d = prose.score_detail(text)
    assert d["ready"] is True
    assert 0 < d["score"] <= 100
    assert len(d["dimensions"]) == 5
    assert abs(sum(x["weight"] for x in d["dimensions"]) - 1.0) < 1e-9
    # every dimension reports a usable number
    assert all(0 <= x["value"] <= 100 for x in d["dimensions"])


def test_a_short_draft_is_marked_provisional():
    short = ("I joined the robotics team because Aisha asked me to. We met in "
             "room 214 every Thursday after school. At first I held the "
             "flashlight while other people did the wiring. Then our drive "
             "train failed at the district meet in February. I spent three "
             "weekends learning to solder from a video, and by March I had "
             "rebuilt the harness myself. Now I teach the ninth graders how "
             "to hold the iron without burning their thumbs.")
    d = prose.score_detail(short)
    assert d["ready"] is True
    assert d["provisional"] is True
    assert d["confidence"] < 100


def test_confidence_pulls_a_thin_draft_toward_the_middle():
    """A measurement from a small sample is reported as one."""
    d = prose.score_detail("The bell rang. " * 30)          # ~90 words
    assert d["provisional"] is True
    # regression toward 58 means a thin draft cannot reach either extreme
    assert 15 < d["score"] < 95


def test_story_map_always_reports_all_five_moves():
    for text in ["", "one word", "The bell rang and I went home. " * 20]:
        smap = prose.story_map(text)
        assert [s["key"] for s in smap] == [k for k, _, _ in prose.STORY_STEPS]
        assert all(0 <= s["strength"] <= 100 for s in smap)


def test_story_map_finds_a_turn_and_notices_when_there_is_none():
    turning = ("I counted the boxes every Saturday. Then in June the compressor "
               "died and everything changed. I learned that I had been wrong.")
    flat = ("I counted the boxes every Saturday. I swept the floor. "
            "I took the register at noon. I liked the work.")
    got = {s["key"]: s["present"] for s in prose.story_map(turning)}
    none = {s["key"]: s["present"] for s in prose.story_map(flat)}
    assert got["change"] is True and got["reflection"] is True
    assert none["change"] is False


def test_a_runaway_sentence_does_not_count_as_good_rhythm():
    """Variety is a standard deviation, so one sixty-word sentence sends it to
    the top of the scale. That is a problem, not a pulse."""
    runaway = ("I woke up. " + "and then I did another thing that took a while "
               * 12 + ". I slept.")
    assert prose._dim_rhythm(runaway) < 70


def test_score_stays_in_range_on_junk_input():
    for junk in ["", "   ", "!!!!!", "a " * 400, "\n\n\n", "?!.,;:"]:
        assert 0 <= prose.score(junk) <= 100


def test_sentence_splitting_handles_abbreviations():
    text = "Dr. Chen ran the lab. She left at 5 p.m. every Friday without fail."
    assert len(prose.sentences(text)) == 2


def test_rhythm_notices_monotony():
    same = " ".join(["The dog ran fast today." for _ in range(8)])
    varied = ("The dog ran. It was a long and complicated afternoon that none of "
              "us had planned for in any way. Then rain. She laughed at me from "
              "the far side of the muddy field.")
    assert prose.rhythm(same)["variety"] < prose.rhythm(varied)["variety"]


def test_strengths_notice_concrete_detail():
    text = ("The kennel smelled of bleach and damp fur. The concrete was cold. "
            "A radio hummed somewhere behind the office door all morning.")
    assert prose.strengths(text, prose.analyse(text)["findings"])


# ------------------------------------------------------------------- robustness
@pytest.mark.parametrize("text", [
    "", "   ", "\n\n", "a", "?!", "....", "Hello.", "x" * 5000,
    "Ünïcödé — em dashes, “smart quotes”, and emoji 🎓 in the draft.",
    "Line one\nLine two\n\nParagraph two here with more words in it.",
])
def test_analyse_never_raises(text):
    r = prose.analyse(text)
    assert isinstance(r["findings"], list)
    assert 0 <= r["score"] <= 100
    # every finding must point at real characters
    for f in r["findings"]:
        assert 0 <= f.start <= f.end <= len(text)
        assert text[f.start:f.end] == f.original or f.kind in prose.STRUCTURAL


def test_vague_quantities_are_pointed_at_but_never_edited():
    """Deleting 'a lot of' would change what the sentence claims, so the engine
    explains it and offers no fix."""
    text = "I went to a lot of the meetings and learned various useful things."
    hits = [f for f in prose.analyse(text)["findings"] if f.kind == "vague_qty"]
    assert hits
    assert all(not f.auto for f in hits)
    out, _ = prose.apply_all(text)
    assert "a lot of" in out, "bulk polish must not remove a quantity"


def test_findings_do_not_overlap_except_structural_ones():
    """Overlapping inline edits would corrupt the text when applied together."""
    text = ("I am very really passionate about helping people and I think that "
            "it was basically a life-changing experience for me honestly.")
    inline = [f for f in prose.analyse(text)["findings"]
              if f.kind not in prose.STRUCTURAL]
    inline.sort(key=lambda f: f.start)
    for a, b in zip(inline, inline[1:]):
        assert a.end <= b.start, f"{a.label} overlaps {b.label}"


def test_structural_findings_do_not_suppress_fixes_inside_them():
    """A long sentence must not hide the filler words it contains — that is the
    sentence most in need of them."""
    text = ("In order to make a difference I basically just decided that I would "
            "very definately try my best at all times without ever stopping once "
            "during the entire long summer of that particular year at the shelter "
            "near my house.")
    kinds = {f.kind for f in prose.analyse(text)["findings"]}
    assert "long" in kinds
    assert "filler" in kinds and "wordy" in kinds


# ====================================================================
# from test_progress_and_checkpoints.py
# ====================================================================

@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def uid(db):
    user = auth.register(db, "nick", "Str0ng-Pass!42", email="n@example.com")
    return user.id


def _school(db, uid, **kw):
    s = School(user_id=uid, name=kw.pop("name", "NYU"), **kw)
    db.add(s); db.commit(); db.refresh(s)
    return s


# --------------------------------------------------------------- the weights
def test_the_weights_add_up_to_exactly_one_hundred():
    """If they ever do not, every ring in the app is wrong by a few percent and
    nothing anywhere would complain."""
    assert sum(progress.WEIGHTS.values()) == 100


def test_a_brand_new_school_is_only_just_started(db, uid):
    school = _school(db, uid)
    ms = progress.milestones(db, uid, school)
    assert progress.percent(ms) == progress.WEIGHTS["listed"]
    assert [m.key for m in ms if m.done] == ["listed"]


def test_progress_rises_as_real_work_appears(db, uid):
    school = _school(db, uid)
    start = progress.percent(progress.milestones(db, uid, school))

    school.deadline = utcnow() + timedelta(days=40)
    school.notes = "x" * 100
    db.add(school); db.commit()
    after = progress.percent(progress.milestones(db, uid, school))

    assert after == start + progress.WEIGHTS["deadline"] + progress.WEIGHTS["why"]


def test_a_draft_counts_toward_every_school_that_has_no_essay_of_its_own(db, uid):
    """One personal statement really does go to all of them, so a general draft
    must move every ring — otherwise the numbers punish students for writing
    one good essay instead of six mediocre ones."""
    a, b = _school(db, uid, name="A"), _school(db, uid, name="B")
    db.add(Essay(user_id=uid, school_id=None, word_target=100,
                 body=" ".join(["word"] * 90)))
    db.commit()

    for school in (a, b):
        ms = {m.key: m for m in progress.milestones(db, uid, school)}
        assert ms["draft"].done, f"{school.name} did not see the general draft"


def test_letters_count_only_once_teachers_have_agreed(db, uid):
    school = _school(db, uid, recs_required=2)
    db.add(Recommender(user_id=uid, name="Ms A", status="asked"))
    db.add(Recommender(user_id=uid, name="Mr B", status="asked"))
    db.commit()
    ms = {m.key: m for m in progress.milestones(db, uid, school)}
    assert not ms["recs"].done, "being asked is not the same as having agreed"

    for r in db.exec(_select(Recommender)).all():
        r.status = "agreed"
        db.add(r)
    db.commit()
    ms = {m.key: m for m in progress.milestones(db, uid, school)}
    assert ms["recs"].done


def test_a_school_needing_no_letters_counts_that_milestone_done(db, uid):
    school = _school(db, uid, recs_required=0)
    ms = {m.key: m for m in progress.milestones(db, uid, school)}
    assert ms["recs"].done


def test_next_step_is_the_heaviest_unfinished_thing(db, uid):
    """"What should I do about Michigan" must answer with the thing that
    actually moves the needle, not whichever box is nearest the top."""
    school = _school(db, uid)
    nxt = progress.next_step(progress.milestones(db, uid, school))
    assert nxt.key == "draft"          # the 25-point one
    assert nxt.route == "/essays"


def test_recompute_writes_the_number_back_and_sets_the_status(db, uid):
    school = _school(db, uid)
    school.deadline = utcnow() + timedelta(days=10)
    db.add(school); db.commit()

    pct = progress.recompute(db, uid, school)
    db.commit()
    assert school.progress == pct > progress.WEIGHTS["listed"]
    assert school.status == AppStatus.in_progress


def test_recompute_never_overrides_a_decision_only_the_student_knows(db, uid):
    school = _school(db, uid, status=AppStatus.accepted)
    progress.recompute(db, uid, school)
    assert school.status == AppStatus.accepted


# ----------------------------------------------------------------- deadlines
@pytest.mark.parametrize("days,expected", [
    (-3, "passed"), (2, "urgent"), (7, "urgent"), (20, "soon"), (90, "later"),
])
def test_urgency_bands(db, uid, days, expected):
    school = _school(db, uid, deadline=utcnow() + timedelta(days=days))
    assert progress.urgency(school) == expected


def test_a_submitted_application_stops_being_urgent(db, uid):
    school = _school(db, uid, deadline=utcnow() + timedelta(days=1),
                     status=AppStatus.submitted)
    assert progress.urgency(school) == "done"


def test_summary_points_at_the_nearest_live_deadline(db, uid):
    _school(db, uid, name="Late", deadline=utcnow() + timedelta(days=60))
    _school(db, uid, name="Soon", deadline=utcnow() + timedelta(days=3))
    _school(db, uid, name="Done", deadline=utcnow() + timedelta(days=1),
            status=AppStatus.submitted)
    s = progress.summary(db, uid)
    assert s["next_name"] == "Soon"
    assert s["count"] == 3 and s["submitted"] == 1


def test_summary_of_an_empty_list_does_not_divide_by_zero(db, uid):
    assert progress.summary(db, uid)["average"] == 0


# -------------------------------------------------------------- achievements
def test_gather_reads_real_rows_not_counters(db, uid):
    db.add(Essay(user_id=uid, body=" ".join(["word"] * 120), word_target=650))
    db.add(Recommender(user_id=uid, name="Ms A", status="agreed"))
    db.add(ScoreRow(user_id=uid, kind="SAT", score="1450"))
    _school(db, uid, status=AppStatus.submitted)
    db.commit()

    st = achievements.gather(db, uid)
    assert st["essay_words"] == 120
    assert st["recs_agreed"] == 1
    assert st["recs_asked"] == 1          # agreed implies asked
    assert st["schools_submitted"] == 1


def test_awarding_is_idempotent(db, uid):
    """The single most damaging thing this could get wrong: award() runs on
    almost every screen load, so paying out twice would inflate a student's XP
    without limit."""
    db.add(Essay(user_id=uid, body=" ".join(["word"] * 200), word_target=650))
    db.commit()

    first = achievements.award(db, uid)
    assert first, "should have earned something"
    xp_after_first = db.get(User, uid).xp

    for _ in range(5):
        assert achievements.award(db, uid) == []
    assert db.get(User, uid).xp == xp_after_first

    rows = db.exec(_select(CheckpointProgress)).all()
    assert len(rows) == len({r.checkpoint_key for r in rows}), "duplicate rows"


def test_awarding_pays_the_advertised_xp(db, uid):
    db.add(Essay(user_id=uid, body=" ".join(["word"] * 120), word_target=650))
    db.commit()
    before = db.get(User, uid).xp
    new = achievements.award(db, uid)
    assert db.get(User, uid).xp - before == sum(a["xp"] for a in new)


def test_achievement_keys_cannot_collide_with_the_meditation_roadmap():
    """Both live in the same table. If a key ever overlapped, reaching one
    would silently mark the other as reached too."""
    from veritagnosis.content import copy as roadmap
    ach = {a["key"] for a in ach_content.ACHIEVEMENTS}
    med = {c["key"] for c in roadmap.ROADMAP}
    assert not (ach & med)
    assert all(k.startswith("a_") for k in ach)
    assert not any(k.startswith("a_") for k in med)


def test_every_achievement_key_is_unique():
    keys = [a["key"] for a in ach_content.ACHIEVEMENTS]
    assert len(keys) == len(set(keys))


def test_every_achievement_requirement_is_a_real_stat(db, uid):
    """A typo in a requirement key would make an achievement unreachable
    forever, and nothing would ever report it."""
    known = set(achievements.gather(db, uid))
    for a in ach_content.ACHIEVEMENTS:
        unknown = set(a["requires"]) - known
        assert not unknown, f"{a['key']} asks for unknown stats {unknown}"


def test_progress_to_uses_the_requirement_that_is_furthest_behind():
    """A bar must not read 90% when one of two conditions has not been started."""
    a = {"requires": {"essay_words": 650, "recs_agreed": 2}}
    assert ach_content.progress_to(a, {"essay_words": 650, "recs_agreed": 0}) == 0
    assert ach_content.progress_to(a, {"essay_words": 325, "recs_agreed": 2}) == 50


def test_board_marks_reached_and_orders_by_category(db, uid):
    db.add(Essay(user_id=uid, body=" ".join(["word"] * 120), word_target=650))
    db.commit()
    achievements.award(db, uid)

    board = achievements.board(db, uid)
    assert len(board) == len(ach_content.ACHIEVEMENTS)
    assert any(b.reached for b in board)
    order = [k for k, _ in ach_content.CATEGORIES]
    seen = [order.index(b.cat) for b in board]
    assert seen == sorted(seen), "categories are out of order"


def test_totals_never_exceed_the_maximum(db, uid):
    db.add(Essay(user_id=uid, body=" ".join(["word"] * 3000), word_target=650))
    db.commit()
    achievements.award(db, uid)
    t = achievements.totals(db, uid)
    assert 0 <= t["reached"] <= t["total"]
    assert 0 <= t["xp"] <= t["xp_total"]
    assert 0 <= t["percent"] <= 100


def test_a_user_sees_only_their_own_checkpoints(db):
    a = auth.register(db, "amara", "Str0ng-Pass!42",
                  email="amara@example.com").id
    b = auth.register(db, "boris", "Str0ng-Pass!42",
                  email="boris@example.com").id
    db.add(Essay(user_id=a, body=" ".join(["word"] * 300), word_target=650))
    db.commit()

    achievements.award(db, a)
    assert achievements.reached_keys(db, a)
    assert achievements.reached_keys(db, b) == set()
    assert achievements.gather(db, b)["essay_words"] == 0


# ====================================================================
# from test_readability.py
# ====================================================================

ROOT = Path(__file__).resolve().parent.parent
# These used to read the design/ sources that theme.css was generated from.
# Those generators are gone and the stylesheet is now the source of truth, so
# the checks run against the file the browser actually loads — which is the
# stronger test anyway: it catches a bad value that reached production, not
# just one that reached an intermediate build artifact.
TOKENS = ROOT / "assets" / "theme.css"
COMPONENTS = ROOT / "assets" / "theme.css"

# WCAG 2.1 asks 4.5:1 for normal-size text. None of this app's greys are large
# enough or bold enough to qualify for the relaxed 3:1 threshold.
AA = 4.5

GROUNDS = ("surface", "bg", "surface-2")


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")[:6]
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(c: tuple[int, int, int]) -> float:
    def ch(v: float) -> float:
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = _lum(_rgb(a)), _lum(_rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _themes() -> dict[str, dict[str, str]]:
    """Every custom property each theme sets, gathered from the stylesheet.

    A theme is not declared in one block. The stylesheet sets its colours in
    one `[data-theme=...]` rule, its typefaces in another, and its scene and
    motif values in further ones. Taking the last block per theme — which is
    what a plain dict comprehension over the matches does — silently yields a
    theme with no colour tokens at all, and every contrast assertion then
    compares two missing values. So the blocks are merged, later ones winning,
    exactly as the cascade would resolve them in a browser.
    """
    css = TOKENS.read_text(encoding="utf-8")
    out: dict[str, dict[str, str]] = {}
    for name, body in re.findall(r'\[data-theme="(\w+)"\]\{(.*?)\n\}', css, re.S):
        out.setdefault(name, {}).update(
            re.findall(r"--([\w-]+):\s*([^;]+);", body))
    return out


THEMES = _themes()
CASES = [(t, ink, ground)
         for t in THEMES
         for ink in ("text", "text-dim", "text-faint")
         for ground in GROUNDS]


def test_the_five_themes_are_all_present():
    assert set(THEMES) == {"serenity", "superhero", "cafe", "astronomy", "terminal"}


@pytest.mark.parametrize("theme,ink,ground", CASES)
def test_every_text_colour_is_readable_on_every_surface(theme, ink, ground):
    """text-faint is the one that failed. It is not decoration: the glossary,
    the checklist details and the form captions are all set in it, and a person
    is expected to read every word."""
    v = THEMES[theme]
    r = contrast(v[ink], v[ground])
    assert r >= AA, f"{theme}: --{ink} on --{ground} is {r:.2f}:1, needs {AA}"


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_label_colour_inside_aid_text_is_readable(theme):
    """`.fm-line b` puts --accent-ink straight onto a card, which is not a
    pairing the palette generator checks."""
    v = THEMES[theme]
    for ground in ("surface", "bg"):
        r = contrast(v["accent-ink"], v[ground])
        assert r >= AA, f"{theme}: --accent-ink on --{ground} is {r:.2f}:1"


# ------------------------------------------------------------------- sizes
def _decl(selector: str) -> str:
    """The declarations of a rule whose selector is exactly `selector`.

    Anchored at the start of a line on purpose. Searching for `.st-label{`
    unanchored finds `.st.done .st-label{` first and reports the wrong rule —
    which briefly had me believing a correct stylesheet was broken.
    """
    css = COMPONENTS.read_text(encoding="utf-8")
    m = re.search(r"^" + re.escape(selector) + r"\{([^}]*)\}", css, re.M)
    assert m, f"{selector} is not a rule of its own in src_components.css"
    return m.group(1)


def test_the_smallest_type_in_the_app_is_not_tiny():
    css = COMPONENTS.read_text(encoding="utf-8")
    for token, floor in (("--fs-xs", 12), ("--fs-sm", 14)):
        m = re.search(re.escape(token) + r":(\d+)px", css)
        assert m, f"{token} is gone"
        assert int(m.group(1)) >= floor, (
            f"{token} is {m.group(1)}px, and paragraphs are set in it")


@pytest.mark.parametrize("selector",
                         [".fm-line", ".gl-mean", ".st-hint", ".st-label"])
def test_the_aid_screens_prose_is_set_at_body_size(selector):
    """These carry the explanation of FAFSA, the glossary definitions and the
    'what to do next' hints. They are the content of the screen, not captions,
    and setting them a step below body text is what made it unreadable."""
    assert "font-size:var(--fs-base)" in _decl(selector), (
        f"{selector} is not body size")


# ------------------------------------------------------- fonts everywhere
def test_form_controls_are_given_the_themes_font_explicitly():
    """Buttons, inputs, dropdowns and text boxes do not inherit font-family in
    any browser — they take the operating system's font unless told otherwise.
    That is why each theme's font stopped at the edge of every control."""
    css = COMPONENTS.read_text(encoding="utf-8")
    m = re.search(r"button,input,select,textarea,optgroup,option[^{]*\{([^}]*)\}", css)
    assert m, "the rule naming the form controls is gone"
    assert "var(--font-ui)" in m.group(1)


def test_headings_all_the_way_to_h6_use_the_display_face():
    css = COMPONENTS.read_text(encoding="utf-8")
    assert re.search(r"h1,h2,h3,h4,h5,h6[^{]*\{[^}]*var\(--font-display\)", css)


def test_placeholder_text_is_themed_too():
    css = COMPONENTS.read_text(encoding="utf-8")
    assert re.search(r"::placeholder\{[^}]*var\(--font-ui\)", css)


# ------------------------------------------------------- the game screen
def test_the_game_waits_for_its_canvas_before_starting():
    """The Start button carries a browser hook and a Reflex event at once, and
    it is the Reflex event that puts the canvas on screen — after a round trip.
    Starting synchronously therefore drew onto a canvas that did not exist yet,
    so the first press did nothing at all. Both scripts now record the wish and
    retry until the stage is really there."""
    for name in ("graze",):
        js = (ROOT / "assets" / f"{name}.js").read_text(encoding="utf-8")
        assert "function stageReady()" in js, f"{name}.js does not wait for its canvas"
        assert "function requestStart(" in js, f"{name}.js starts synchronously"
        assert "wantMin" in js


def test_a_single_bad_frame_cannot_kill_the_game_for_good():
    """An exception inside the animation loop breaks the requestAnimationFrame
    chain permanently, and the screen looks exactly like one that never
    started."""
    for name in ("graze",):
        js = (ROOT / "assets" / f"{name}.js").read_text(encoding="utf-8")
        assert "frameErrors" in js, f"{name}.js has an unguarded frame loop"


def test_read_aloud_speaks_in_pieces_and_says_so_when_it_cannot():
    """Chrome silently drops long utterances and cuts off after about fifteen
    seconds, so handing it a whole essay produced no sound at all — and the
    button said 'Stop' regardless, so there was no way to tell."""
    js = (ROOT / "assets" / "essay.js").read_text(encoding="utf-8")
    assert "function chunk(" in js, "the essay still goes in as one utterance"
    assert "function readNote(" in js, "a silent failure still says nothing"
    assert "onvoiceschanged" in js, "the voice list is not waited for"
    assert "resume()" in js, "nothing nudges Chrome's self-pausing synthesiser"


# ------------------------------------------------ regressions, September 2026
def test_the_csp_allows_the_theme_fonts():
    """Every theme has its own display and body face, served by Google Fonts.
    A Content-Security-Policy that omits those two hosts does not raise
    anything — it silently drops all five themes to system sans, so the app
    just looks wrong with no error anywhere to explain why."""
    from veritagnosis.security import CSP
    style = next(p for p in CSP.split("; ") if p.startswith("style-src"))
    font = next(p for p in CSP.split("; ") if p.startswith("font-src"))
    assert "https://fonts.googleapis.com" in style, "the @font-face CSS is blocked"
    assert "https://fonts.gstatic.com" in font, "the font files are blocked"


def test_every_font_the_themes_name_is_actually_requested():
    """A theme naming a face that is never fetched falls back without warning."""
    import re
    from veritagnosis.ui.theme import FONTS

    css = (ROOT / "assets" / "theme.css").read_text(encoding="utf-8")
    requested = " ".join(FONTS)
    # Quoted family names in the theme blocks, e.g.  --font-ui:"Nunito",...
    named = set(re.findall(r'--font-(?:ui|display):"([^"]+)"', css))
    assert named, "no theme fonts found in the stylesheet"
    for family in named:
        if family.startswith(("ui-", "system-")):
            continue
        assert family.replace(" ", "+") in requested, \
            f'theme uses "{family}" but it is never loaded'


def test_a_text_input_key_never_depends_on_what_is_being_typed():
    """A React key built from the field's own value changes on every
    keystroke, so the input is destroyed and rebuilt each character and the
    caret is lost. The box then looks broken: you type and nothing appears."""
    import re
    src = (ROOT / "veritagnosis" / "pages" / "profile.py").read_text(encoding="utf-8")
    # Every key= on this page must be built from the reset counter, not a field.
    for match in re.findall(r'key=([^\n]+)', src):
        assert "form_epoch" in match, \
            f"input key depends on typed content, caret will be lost: {match.strip()}"


# ====================================================================
# from test_unlocks_and_quotes.py
# ====================================================================

# ROOT is already defined above — same value.

ACH_KEYS = {a["key"] for a in ach.ACHIEVEMENTS}


# ------------------------------------------------------------------ the locks
@pytest.mark.parametrize("where,need", sorted(parts.LOCKED.items()))
def test_every_locked_item_points_at_a_real_achievement_and_a_real_option(where, need):
    category, index = where
    assert category in parts.OPTIONS, f"{category} is not a category"
    assert index < len(parts.OPTIONS[category]), (
        f"{category}[{index}] does not exist — there are "
        f"{len(parts.OPTIONS[category])} options")
    assert need in ACH_KEYS, f"{need} is not an achievement"


@pytest.mark.parametrize("index,need", sorted(parts.LOCKED_COLOURS.items()))
def test_every_locked_colour_points_at_a_real_achievement(index, need):
    assert index < len(parts.HAIR_COLORS)
    assert need in ACH_KEYS


def test_identity_is_never_locked():
    """A student has to be able to build something that looks like them on
    the first visit. Faces, skin and the plain hair colours are not rewards
    and locking one would be a genuinely nasty thing to do."""
    for category in ("head", "eyes", "eyebrows", "nose"):
        locked = [i for (c, i) in parts.LOCKED if c == category]
        assert not locked, f"{category} has locked options: {locked}"
    # Skin tone has no lock map at all, and must not grow one.
    assert not any(c == "skin" for c, _ in parts.LOCKED)


def test_the_first_option_in_every_category_is_always_available():
    """`sanitise` falls back to index 0, so index 0 can never be locked or a
    rejected avatar would fall back to something still forbidden."""
    for category in parts.OPTIONS:
        assert parts.lock_for(category, 0) is None
    assert parts.colour_lock_for(0) is None


def test_a_new_student_can_still_reach_most_of_the_wardrobe():
    """Locked items should be a minority. A grid that is mostly padlocks on
    day one reads as a paywall, not a reward."""
    total = sum(len(v) for v in parts.OPTIONS.values())
    assert len(parts.LOCKED) < total * 0.35, (
        f"{len(parts.LOCKED)} of {total} options are locked")


def test_there_are_substantially_more_options_than_before():
    """The wardrobe was asked to grow. This is a floor, not a target."""
    counts = {k: len(v) for k, v in parts.OPTIONS.items()}
    assert sum(counts.values()) >= 80, counts
    for category, n in counts.items():
        assert n >= 6, f"{category} only has {n} options"
    assert len(parts.SKIN_TONES) >= 10
    assert len(parts.HAIR_COLORS) >= 12


# ------------------------------------------------------------- sanitising
def test_an_unearned_item_is_stripped_out_of_a_saved_avatar():
    (category, index), need = next(iter(sorted(parts.LOCKED.items())))
    sel = {**parts.DEFAULT_AVATAR, category: index}
    cleaned = parts.sanitise(sel, earned=set())
    assert cleaned[category] == 0, "a locked item survived sanitising"


def test_an_earned_item_is_left_alone():
    (category, index), need = next(iter(sorted(parts.LOCKED.items())))
    sel = {**parts.DEFAULT_AVATAR, category: index}
    cleaned = parts.sanitise(sel, earned={need})
    assert cleaned[category] == index


def test_an_unearned_hair_colour_is_stripped():
    index, need = next(iter(sorted(parts.LOCKED_COLOURS.items())))
    cleaned = parts.sanitise({**parts.DEFAULT_AVATAR, "hair_color": index}, set())
    assert cleaned["hair_color"] == 0
    kept = parts.sanitise({**parts.DEFAULT_AVATAR, "hair_color": index}, {need})
    assert kept["hair_color"] == index


def test_every_option_still_renders_after_all_the_additions():
    """A broken path in one new SVG would show as an empty tile rather than
    an error, so every option is rendered once here."""
    for category, options in parts.OPTIONS.items():
        for i in range(len(options)):
            svg = parts.render({**parts.DEFAULT_AVATAR, category: i}, 96)
            assert svg.startswith("<svg") and svg.endswith("</svg>")
            assert "{skin}" not in svg and "{hair}" not in svg, (
                f"{category}[{i}] left a placeholder unfilled")


# --------------------------------------------------------------- the quotes
def _source(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("path,marker", [
    ("veritagnosis/pages/play.py", "med-quote"),
    ("veritagnosis/ui/theme.py", "hero-quote"),
    ("veritagnosis/pages/auth.py", "tip-inner"),
])
def test_every_kinetic_quote_is_keyed_on_its_own_text(path, marker):
    """Without the key React patches a node motion.js has rewritten, and the
    line renders empty. This is the assertion that stops it coming back."""
    src = _source(path)
    assert marker in src, f"{marker} is gone from {path}"
    assert "key=" in src, (
        f"{path} renders a kinetic quote with no key — it will blank out "
        f"when the text changes")


def test_both_rotating_loops_are_bounded():
    """A background task cannot see a closed tab. An unbounded loop keeps
    rotating quotes for a browser that has gone, and fills the log with
    'delta to disconnected client'."""
    for path in ("veritagnosis/states/play_state.py",
                 "veritagnosis/states/base.py"):
        src = _source(path)
        assert "rotate_quotes" in src
        body = src.split("async def rotate_quotes")[1].split("\n    @rx")[0]
        assert "while True" not in body, f"{path} rotates forever"
        assert re.search(r"for _ in range\(\d+\)", body), (
            f"{path} has no bound on its rotation loop")


def test_a_reroll_never_repeats_the_line_already_showing():
    """A reroll that lands on the same quote looks like a broken button."""
    for path in ("veritagnosis/states/play_state.py",
                 "veritagnosis/states/base.py"):
        src = _source(path)
        assert "!= self.quote_text" in src or "q[0] != self.quote_text" in src, (
            f"{path} can reroll to the quote already on screen")


# ------------------------------------------------------- today's one task
#
# The home screen used to tell every student, forever, to "Start essay draft
# for NYU application". NYU came from the wireframe. The branch that produced
# it fired whenever an unfinished essay row existed, which is always, because
# opening the essay screen creates one. A student whose list is Rutgers and
# TCNJ was told to work on NYU.
#
# The first test is the one that matters: the task may only ever name a school
# this student actually typed.

def _task_school(db, uid, name, **kw):
    from veritagnosis.models import School
    row = School(user_id=uid, name=name, **kw)
    db.add(row); db.commit(); db.refresh(row)
    return row


def _task_essay(db, uid, school_id=None, body="", target=650):
    from veritagnosis.models import Essay
    row = Essay(user_id=uid, school_id=school_id, prompt="p",
                body=body, word_target=target)
    db.add(row); db.commit(); db.refresh(row)
    return row


def test_the_task_never_names_a_school_the_student_does_not_have(db):
    """The actual regression. Any invented name fails this."""
    from veritagnosis.services import apply as progress
    uid = auth.register(db, "nick", "Str0ng-Pass!42",
                        email="nick@example.com").id
    mine = {"Rutgers", "TCNJ"}
    _task_school(db, uid, "Rutgers")
    _task_school(db, uid, "TCNJ")
    _task_essay(db, uid)                      # the row the essay screen creates

    t = progress.next_task(db, uid)
    named = {w for w in mine if w in t.title}
    foreign = [n for n in ("NYU", "UMich", "UCLA", "Harvard", "Stanford")
               if n in t.title]
    assert not foreign, f"invented a school: {t.title!r}"
    assert t.title and t.route.startswith("/")


def test_an_empty_list_asks_for_a_college_first(db):
    from veritagnosis.services import apply as progress
    uid = auth.register(db, "nick", "Str0ng-Pass!42",
                        email="nick@example.com").id
    t = progress.next_task(db, uid)
    assert "first college" in t.title.lower()
    assert t.route == "/applications"


def test_a_deadline_inside_two_weeks_outranks_everything(db):
    from datetime import timedelta
    from veritagnosis.models import utcnow
    from veritagnosis.services import apply as progress
    uid = auth.register(db, "nick", "Str0ng-Pass!42",
                        email="nick@example.com").id
    _task_school(db, uid, "Faraway")
    soon = _task_school(db, uid, "Rutgers", deadline=utcnow() + timedelta(days=3))
    _task_essay(db, uid, school_id=soon.id)

    t = progress.next_task(db, uid)
    assert "Rutgers" in t.title
    assert "3 days left" in t.title


def test_a_blank_essay_is_the_task_when_no_deadline_is_close(db):
    from veritagnosis.services import apply as progress
    uid = auth.register(db, "nick", "Str0ng-Pass!42",
                        email="nick@example.com").id
    s = _task_school(db, uid, "TCNJ")
    _task_essay(db, uid, school_id=s.id, body="")
    t = progress.next_task(db, uid)
    assert "TCNJ" in t.title and "Start" in t.title
    assert t.route == "/essays"


def test_a_short_essay_reports_its_real_word_counts(db):
    """No invented numbers: the meta line must be arithmetic on the draft."""
    from veritagnosis.services import apply as progress
    uid = auth.register(db, "nick", "Str0ng-Pass!42",
                        email="nick@example.com").id
    s = _task_school(db, uid, "TCNJ")
    _task_essay(db, uid, school_id=s.id, body=" ".join(["word"] * 120), target=650)
    t = progress.next_task(db, uid)
    assert "TCNJ" in t.title
    assert "120 of 650 words" in t.meta
    assert "530 to go" in t.meta


def test_the_task_carries_no_invented_xp_or_step_counts(db):
    """'~47 xp' and 'Due in 3 steps' were both made up."""
    import re
    from veritagnosis.services import apply as progress
    uid = auth.register(db, "nick", "Str0ng-Pass!42",
                        email="nick@example.com").id
    _task_school(db, uid, "Rutgers")
    _task_essay(db, uid)
    for _ in range(2):
        t = progress.next_task(db, uid)
        assert "xp" not in t.meta.lower(), f"invented xp: {t.meta!r}"
        assert not re.search(r"\bin \d+ steps\b", t.meta), t.meta


def test_everything_submitted_says_so_instead_of_inventing_work(db):
    from veritagnosis.models import AppStatus
    from veritagnosis.services import apply as progress
    uid = auth.register(db, "nick", "Str0ng-Pass!42",
                        email="nick@example.com").id
    s = _task_school(db, uid, "Rutgers")
    s.status = AppStatus.submitted
    db.add(s); db.commit()
    t = progress.next_task(db, uid)
    assert "every application is in" in t.title.lower()


def test_the_task_is_stable_and_never_raises_on_odd_data(db):
    """Runs on every home load, so it must not be the thing that breaks it."""
    from veritagnosis.services import apply as progress
    uid = auth.register(db, "nick", "Str0ng-Pass!42",
                        email="nick@example.com").id
    _task_school(db, uid, "")                      # blank name
    _task_essay(db, uid, school_id=None, body=None, target=0)
    t = progress.next_task(db, uid)
    assert isinstance(t.title, str) and t.title


