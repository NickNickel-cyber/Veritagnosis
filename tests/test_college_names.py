"""College names: nicknames become full names, and nothing ambiguous is guessed.

A list that says "UMich" found no data, because the catalogue only knows full
names. These tests pin the three rules that fixed it: a nickname resolves to
the official full name, a full name matches however it is punctuated, and a
name that could mean several colleges is offered as a choice, never guessed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from veritagnosis.content.colleges import ALIASES, COLLEGES
from veritagnosis.models import College, School, Tier, User
from veritagnosis.services import catalog, insight

SCORECARD = [
    # unitid, name, state, size
    (170976, "University of Michigan-Ann Arbor", "MI", 34000),
    (171137, "University of Michigan-Dearborn", "MI", 6000),
    (171146, "University of Michigan-Flint", "MI", 5000),
    (110662, "University of California-Los Angeles", "CA", 33000),
    (186380, "Rutgers University-New Brunswick", "NJ", 37000),
    (185828, "Rutgers University-Newark", "NJ", 9000),
    (186371, "Rutgers University-Camden", "NJ", 4000),
    (186131, "The College of New Jersey", "NJ", 7000),
    (211440, "Carnegie Mellon University", "PA", 7300),
]


@pytest.fixture()
def db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path/'names.db'}",
                           connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    from veritagnosis import db as dbmod
    monkeypatch.setattr(dbmod, "engine", engine)
    monkeypatch.setattr(dbmod, "init_db", lambda: None)
    monkeypatch.setattr(dbmod, "get_session", lambda: Session(engine))
    with Session(engine) as s:
        for unitid, name, state, size in SCORECARD:
            s.add(College(unitid=unitid, name=name,
                          name_key=" ".join(name.lower().split()),
                          state=state, size=size, accept_rate=50.0,
                          cost_year=40000, data_year="test",
                          source_url=f"https://collegescorecard.ed.gov/school/?{unitid}",
                          source_kind="college_scorecard", confidence="medium"))
        s.commit()
        yield s


def _student(s, *names: str) -> int:
    u = User(username=f"names-{len(names)}-{'-'.join(n[:4] for n in names)}",
             password_hash="x")
    s.add(u)
    s.commit()
    s.refresh(u)
    for n in names:
        s.add(School(user_id=u.id, name=n, tier=Tier.target))
    s.commit()
    return u.id


# ------------------------------------------------------------- matching names
def test_punctuation_case_and_a_leading_the_do_not_matter():
    assert catalog.loose("University of Michigan-Ann Arbor") == \
        catalog.loose("university of michigan ann arbor")
    assert catalog.loose("The College of New Jersey") == \
        catalog.loose("College of New Jersey")
    assert catalog.loose("Texas A&M") == catalog.loose("texas a and m")


def test_a_nickname_resolves_to_the_official_full_name(db):
    m = catalog.resolve(db, "UMich")
    assert m is not None
    assert m.name == "University of Michigan-Ann Arbor"


def test_a_full_name_matches_however_it_is_punctuated(db):
    for typed in ("University of Michigan Ann Arbor",
                  "university of michigan-ann arbor",
                  "  University   of Michigan - Ann Arbor "):
        m = catalog.resolve(db, typed)
        assert m is not None and m.name == "University of Michigan-Ann Arbor", typed


def test_the_hand_checked_entry_still_wins_under_its_full_name(db):
    """The curated file stores UCLA under its nickname. A student typing the
    official name must still get the hand-checked figures, not the federal
    average."""
    curated = next(c for c in COLLEGES if c["name"] == "UCLA")
    m = catalog.resolve(db, "University of California-Los Angeles")
    assert m is not None
    assert m.entry is curated
    assert m.name == "University of California-Los Angeles"


def test_a_curated_college_resolves_with_no_import_at_all():
    m = catalog.resolve(None, "UPenn")
    assert m is not None and m.name == "University of Pennsylvania"


def test_an_ambiguous_name_is_not_guessed(db):
    assert catalog.resolve(db, "Rutgers") is None
    names = [c["name"] for c in catalog.suggest(db, "Rutgers")]
    assert names[0] == "Rutgers University-New Brunswick"      # largest first
    assert set(names) >= {"Rutgers University-Newark", "Rutgers University-Camden"}


def test_an_unknown_name_is_none_with_nothing_suggested(db):
    assert catalog.resolve(db, "Zzqx Polytechnic") is None
    assert catalog.suggest(db, "Zzqx Polytechnic") == []


def test_suggestions_are_full_names_and_find_part_typed_nicknames(db):
    got = catalog.suggest(db, "umi")
    assert got and got[0]["name"] == "University of Michigan-Ann Arbor"
    assert got[0]["state"] == "MI"
    names = [c["name"] for c in catalog.suggest(db, "michigan")]
    assert "University of Michigan-Ann Arbor" in names
    assert all(len(n.split()) >= 2 for n in names)    # never a bare nickname


def test_every_suggestion_can_actually_be_added(db):
    """A suggestion the catalogue cannot match would be refused on Add and
    offered again — a loop. Every name offered must resolve."""
    for typed in ("michigan", "umi", "rutgers", "uc", "new jersey", "carn"):
        for c in catalog.suggest(db, typed):
            assert catalog.resolve(db, c["name"]) is not None, (typed, c["name"])


# ------------------------------------------------------- lists already saved
def test_nicknames_on_a_saved_list_become_full_names(db):
    uid = _student(db, "UMich", "UPenn", "Rutgers", "Made Up College")
    assert catalog.tidy_names(db, uid) == 2
    names = sorted(r.name for r in db.exec(
        select(School).where(School.user_id == uid)).all())
    assert names == ["Made Up College", "Rutgers",
                     "University of Michigan-Ann Arbor",
                     "University of Pennsylvania"]
    assert catalog.tidy_names(db, uid) == 0       # a second pass changes nothing


def test_the_profile_review_finds_data_for_a_nickname(db):
    uid = _student(db, "UMich")
    fits = insight.review(uid)["fits"]
    assert len(fits) == 1
    assert fits[0].has_data
    assert fits[0].school_name == "University of Michigan-Ann Arbor"


def test_an_unmatched_college_carries_the_names_it_might_be(db):
    uid = _student(db, "Rutgers")
    fit = insight.review(uid)["fits"][0]
    assert not fit.has_data
    assert fit.school_id > 0
    assert fit.suggestions[0] == "Rutgers University-New Brunswick"


# ---------------------------------------------------------- the nickname table
def test_every_nickname_is_lowercase_and_points_somewhere():
    for k, v in ALIASES.items():
        assert k == k.lower().strip() and v.strip(), k


SEED = Path(__file__).resolve().parents[1] / "data" / "colleges.seed.db"


@pytest.mark.skipif(not SEED.exists(), reason="no imported catalogue on this machine")
def test_every_nickname_target_is_a_real_scorecard_name():
    con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
    names = {r[0] for r in con.execute("select name from college")}
    con.close()
    missing = sorted({v for v in ALIASES.values() if v not in names})
    assert not missing, missing


@pytest.mark.skipif(not SEED.exists(), reason="no imported catalogue on this machine")
def test_no_nickname_shadows_a_different_college():
    """A nickname must never be the full name of some other college, or typing
    that college's real name would send the student somewhere else."""
    con = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
    by_loose = {catalog.loose(r[0]): r[0] for r in con.execute("select name from college")}
    con.close()
    for k, v in ALIASES.items():
        other = by_loose.get(catalog.loose(k))
        assert other in (None, v), (k, other, v)
