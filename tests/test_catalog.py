"""
The college catalogue: the importer, and the rule about which source wins.

The fixture CSV below is deliberately nasty in the ways the real Scorecard file
is nasty: PrivacySuppressed values, NULLs, blanks, closed institutions,
certificate mills, and a name that collides with a curated entry.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from veritagnosis.models import College
from veritagnosis.services import catalog


# UNITID,INSTNM,STABBR,CITY,CONTROL,ADM_RATE,SATVR25,SATVR75,SATMT25,SATMT75,
# ACTCM25,ACTCM75,COSTT4_A,TUITIONFEE_IN,TUITIONFEE_OUT,NPT4_PUB,NPT4_PRIV,
# UGDS,PREDDEG,CURROPER,ICLEVEL
HEADER = ("UNITID,INSTNM,STABBR,CITY,CONTROL,ADM_RATE,SATVR25,SATVR75,"
          "SATMT25,SATMT75,ACTCM25,ACTCM75,COSTT4_A,TUITIONFEE_IN,"
          "TUITIONFEE_OUT,NPT4_PUB,NPT4_PRIV,UGDS,PREDDEG,CURROPER,ICLEVEL")

ROWS = [
    # a normal public university, complete data
    "186380,Rutgers University-New Brunswick,NJ,New Brunswick,1,0.6612,"
    "600,700,620,760,27,33,36000,15804,33005,21000,NULL,36039,3,1,1",
    # private, net price in the PRIVATE column, no ACT published
    "186131,The College of New Jersey,NJ,Ewing,2,0.6089,"
    "590,680,580,680,NULL,NULL,42000,18000,31000,NULL,24000,7000,3,1,1",
    # scores suppressed, cost missing — must become None, never 0
    "999001,Tiny Liberal Arts College,VT,Nowhere,2,PrivacySuppressed,"
    "PrivacySuppressed,PrivacySuppressed,NULL,NULL,NULL,NULL,,,"
    ",,,850,3,1,1",
    # closed: CURROPER 0 — must be skipped
    "999002,Closed Forever University,NY,Gone,2,0.5,500,600,500,600,"
    "20,25,30000,20000,20000,NULL,15000,1200,3,0,1",
    # certificate mill: PREDDEG 1 — must be skipped
    "999003,Quick Certificates Institute,FL,Miami,3,NULL,NULL,NULL,NULL,"
    "NULL,NULL,NULL,12000,9000,9000,NULL,8000,400,1,1,2",
    # no undergraduates — must be skipped
    "999004,Graduate Only School,MA,Boston,2,0.2,NULL,NULL,NULL,NULL,"
    "NULL,NULL,50000,40000,40000,NULL,30000,0,3,1,1",
    # collides with a curated entry; the curated one must win on lookup
    "166027,Harvard University,MA,Cambridge,2,0.0321,"
    "730,780,750,800,33,36,80000,57261,57261,NULL,13000,7000,3,1,1",
]


@pytest.fixture()
def csv_path(tmp_path):
    p = tmp_path / "Most-Recent-Cohorts-Institution_2024.csv"
    p.write_text(HEADER + "\n" + "\n".join(ROWS) + "\n", encoding="utf-8")
    return p


@pytest.fixture()
def db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path/'cat.db'}",
                           connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    from veritagnosis import db as dbmod
    monkeypatch.setattr(dbmod, "engine", engine)
    monkeypatch.setattr(dbmod, "init_db", lambda: None)
    monkeypatch.setattr(dbmod, "get_session", lambda: Session(engine))
    with Session(engine) as s:
        yield s


# ------------------------------------------------------------------ importing

def test_only_bachelors_institutions_that_are_open_get_imported(db, csv_path):
    from scripts.import_colleges import run
    run(str(csv_path), echo=lambda *a: None)
    names = {c.name for c in db.exec(select(College)).all()}
    assert "Rutgers University-New Brunswick" in names
    assert "The College of New Jersey" in names
    assert "Closed Forever University" not in names, "CURROPER 0 must be skipped"
    assert "Quick Certificates Institute" not in names, "PREDDEG 1 must be skipped"
    assert "Graduate Only School" not in names, "no undergraduates must be skipped"


def test_suppressed_and_blank_values_become_none_never_zero(db, csv_path):
    """A zero would be rendered as a real number. None is rendered as unknown."""
    from scripts.import_colleges import run
    run(str(csv_path), echo=lambda *a: None)
    tiny = db.exec(select(College).where(
        College.name == "Tiny Liberal Arts College")).one()
    assert tiny.accept_rate is None
    assert tiny.sat_25 is None and tiny.sat_75 is None
    assert tiny.act_25 is None and tiny.act_75 is None
    assert tiny.cost_year is None
    assert tiny.tuition_in is None
    assert tiny.size == 850


def test_sat_is_summed_into_a_composite_on_the_1600_scale(db, csv_path):
    from scripts.import_colleges import run
    run(str(csv_path), echo=lambda *a: None)
    r = db.exec(select(College).where(College.name_key.contains("rutgers"))).one()
    assert r.sat_25 == 1220      # 600 + 620
    assert r.sat_75 == 1460      # 700 + 760


def test_a_half_missing_sat_is_not_guessed(db, csv_path):
    """Reading without maths is not a composite, and must not be invented."""
    from scripts.import_colleges import run
    run(str(csv_path), echo=lambda *a: None)
    tiny = db.exec(select(College).where(
        College.name == "Tiny Liberal Arts College")).one()
    assert tiny.sat_25 is None


def test_admission_rate_is_stored_as_a_percentage(db, csv_path):
    """The curated entries use percent, so these must too or the fit engine
    would compare 0.66 against 66."""
    from scripts.import_colleges import run
    run(str(csv_path), echo=lambda *a: None)
    r = db.exec(select(College).where(College.name_key.contains("rutgers"))).one()
    assert 66.0 <= r.accept_rate <= 66.2


def test_net_price_comes_from_the_column_matching_the_control(db, csv_path):
    from scripts.import_colleges import run
    run(str(csv_path), echo=lambda *a: None)
    pub = db.exec(select(College).where(College.control == "public")).first()
    priv = db.exec(select(College).where(
        College.name == "The College of New Jersey")).one()
    assert pub.net_price == 21000        # NPT4_PUB
    assert priv.net_price == 24000       # NPT4_PRIV


def test_every_row_carries_a_real_source_url_and_medium_confidence(db, csv_path):
    """The whole design rule: no number without somewhere to check it."""
    from scripts.import_colleges import run
    run(str(csv_path), echo=lambda *a: None)
    for c in db.exec(select(College)).all():
        assert c.source_url.startswith("https://collegescorecard.ed.gov/school/?")
        assert str(c.unitid) in c.source_url
        assert c.confidence == "medium"
        assert c.source_kind == "college_scorecard"
        assert c.data_year == "2024"


def test_importing_twice_updates_rather_than_duplicates(db, csv_path):
    from scripts.import_colleges import run
    first = run(str(csv_path), echo=lambda *a: None)
    second = run(str(csv_path), echo=lambda *a: None)
    assert first == second
    ids = [c.unitid for c in db.exec(select(College)).all()]
    assert len(ids) == len(set(ids))


def test_a_file_that_is_not_the_scorecard_is_refused(db, tmp_path):
    from scripts.import_colleges import run
    bad = tmp_path / "shopping.csv"
    bad.write_text("name,price\nmilk,2\n", encoding="utf-8")
    assert run(str(bad), echo=lambda *a: None) == -1


def test_a_missing_file_is_refused_without_an_exception(db, tmp_path):
    from scripts.import_colleges import run
    assert run(str(tmp_path / "nope.csv"), echo=lambda *a: None) == -1


# ------------------------------------------------------------------- lookup

def test_a_curated_entry_beats_an_imported_one(db, csv_path):
    """Harvard is in both. The hand-read Common Data Set must win."""
    from scripts.import_colleges import run
    run(str(csv_path), echo=lambda *a: None)
    got = catalog.lookup(db, "Harvard University")
    assert got["source_kind"] == "common_data_set"
    assert got["confidence"] == "high"
    assert got["accept_rate"] == 3.6          # the curated figure, not 3.21


def test_an_imported_college_is_found_when_nothing_curated_matches(db, csv_path):
    from scripts.import_colleges import run
    run(str(csv_path), echo=lambda *a: None)
    got = catalog.lookup(db, "the college of new jersey")
    assert got is not None
    assert got["source_kind"] == "college_scorecard"
    assert got["state"] == "NJ"


def test_lookup_is_case_and_space_insensitive(db, csv_path):
    from scripts.import_colleges import run
    run(str(csv_path), echo=lambda *a: None)
    for spelling in ("  RUTGERS UNIVERSITY-NEW BRUNSWICK ",
                     "rutgers university-new brunswick"):
        assert catalog.lookup(db, spelling) is not None


def test_an_unknown_college_is_none_not_a_guess(db, csv_path):
    from scripts.import_colleges import run
    run(str(csv_path), echo=lambda *a: None)
    assert catalog.lookup(db, "Hogwarts") is None
    assert catalog.lookup(db, "") is None


def test_search_prefers_names_that_start_with_the_query(db, csv_path):
    from scripts.import_colleges import run
    run(str(csv_path), echo=lambda *a: None)
    hits = catalog.search(db, "rutgers")
    assert hits and hits[0]["name"].lower().startswith("rutgers")


def test_search_needs_two_characters(db):
    assert catalog.search(db, "r") == []
    assert catalog.search(db, "") == []


def test_search_works_with_no_import_run_yet(db):
    """A fresh install has the curated two dozen and nothing else."""
    assert catalog.is_imported(db) is False
    hits = catalog.search(db, "harvard")
    assert hits and hits[0]["name"] == "Harvard University"
