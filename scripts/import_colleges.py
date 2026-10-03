"""
Import the US Department of Education's College Scorecard into the database.

    python scripts/import_colleges.py <path-to-csv>
    python scripts/manage.py import-colleges <path-to-csv>     (same thing)

Getting the file
----------------
It is free, public, and needs no account:

    https://collegescorecard.ed.gov/data/

Download **"Most Recent Institution-Level Data"**, unzip it, and point this at
the .csv inside. It is a large file — a few hundred megabytes and roughly 3,000
columns — so this reads it as a stream and keeps only the columns below. It
never loads the whole thing into memory.

What gets imported
------------------
Institutions that are currently operating, award bachelor's degrees
predominantly, and have undergraduates. That is the population a student
applying to college is choosing from — roughly 2,000 of the 6,500 rows. The
rest are beauty schools, certificate programmes and closed institutions, and
putting them in the search box would make it worse, not better.

Honesty rules this obeys
------------------------
* Nothing is invented. "PrivacySuppressed", "NULL" and blank all become None,
  and the screens already know how to render a missing number.
* Every row carries the real Scorecard URL for that institution, so a student
  can check any figure.
* Every row is marked confidence="medium", because a federal release averaged
  across a year is good but not as good as the institution's own Common Data
  Set — which is what the two dozen curated entries in content/colleges.py are,
  and why those still win on a name collision. See services/catalog.py.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import select                                    # noqa: E402

from veritagnosis import db                                    # noqa: E402
from veritagnosis.models import College                        # noqa: E402

# Only these columns are read. Naming them keeps memory flat regardless of how
# many thousand columns the release happens to ship with.
WANT = [
    "UNITID", "INSTNM", "STABBR", "CITY", "CONTROL",
    "ADM_RATE", "SATVR25", "SATVR75", "SATMT25", "SATMT75",
    "ACTCM25", "ACTCM75",
    "COSTT4_A", "TUITIONFEE_IN", "TUITIONFEE_OUT",
    "NPT4_PUB", "NPT4_PRIV", "UGDS",
    "PREDDEG", "CURROPER", "ICLEVEL",
]

CONTROL = {"1": "public", "2": "private", "3": "for-profit"}

# Values the Scorecard uses for "we are not telling you this".
BLANK = {"", "null", "none", "privacysuppressed", "na", "n/a"}


def _num(raw: str | None) -> float | None:
    if raw is None:
        return None
    if str(raw).strip().lower() in BLANK:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _int(raw: str | None) -> int | None:
    v = _num(raw)
    return int(round(v)) if v is not None else None


def _sat_total(row: dict) -> tuple[int | None, int | None]:
    """The Scorecard publishes reading and maths separately.

    A composite is their sum, which is how the 1600 scale works and how every
    college quotes it. If either half is missing the composite is not guessed.
    """
    lo = _num(row.get("SATVR25")), _num(row.get("SATMT25"))
    hi = _num(row.get("SATVR75")), _num(row.get("SATMT75"))
    p25 = int(lo[0] + lo[1]) if None not in lo else None
    p75 = int(hi[0] + hi[1]) if None not in hi else None
    return p25, p75


def wanted(row: dict) -> bool:
    """Is this somewhere a college applicant would apply?"""
    if str(row.get("CURROPER", "")).strip() != "1":
        return False
    # PREDDEG 3 = predominantly bachelor's degrees.
    if str(row.get("PREDDEG", "")).strip() != "3":
        return False
    ugds = _num(row.get("UGDS"))
    if ugds is not None and ugds < 1:
        return False
    return bool((row.get("INSTNM") or "").strip())


def to_college(row: dict, data_year: str) -> College:
    sat_25, sat_75 = _sat_total(row)
    rate = _num(row.get("ADM_RATE"))
    name = (row.get("INSTNM") or "").strip()
    unitid = _int(row.get("UNITID")) or 0
    control = CONTROL.get(str(row.get("CONTROL", "")).strip(), "")
    net = _int(row.get("NPT4_PUB")) if control == "public" else _int(row.get("NPT4_PRIV"))

    return College(
        unitid=unitid,
        name=name[:200],
        name_key=" ".join(name.lower().split())[:200],
        state=(row.get("STABBR") or "").strip()[:2],
        city=(row.get("CITY") or "").strip()[:120],
        control=control,
        # Stored as a percentage, because that is what the curated entries use
        # and what every student has seen quoted.
        accept_rate=round(rate * 100, 1) if rate is not None else None,
        sat_25=sat_25, sat_75=sat_75,
        act_25=_int(row.get("ACTCM25")), act_75=_int(row.get("ACTCM75")),
        cost_year=_int(row.get("COSTT4_A")),
        tuition_in=_int(row.get("TUITIONFEE_IN")),
        tuition_out=_int(row.get("TUITIONFEE_OUT")),
        net_price=net,
        size=_int(row.get("UGDS")),
        data_year=data_year,
        source_url=f"https://collegescorecard.ed.gov/school/?{unitid}",
        source_kind="college_scorecard",
        confidence="medium",
        test_optional_note=(
            "Scorecard score ranges describe students who submitted scores. "
            "Where a college is test-optional that is a self-selected group."
            if (sat_25 or row.get("ACTCM25")) else None),
    )


def run(path: str, data_year: str = "", echo=print) -> int:
    """Import the file. Returns how many colleges are in the table afterwards."""
    src = Path(path).expanduser()
    if not src.exists():
        echo(f"  No such file: {src}")
        echo("  Download 'Most Recent Institution-Level Data' from")
        echo("      https://collegescorecard.ed.gov/data/")
        echo("  unzip it, and pass the .csv inside.")
        return -1

    # The release year is in the filename, e.g. Most-Recent-Cohorts-...2024.csv
    if not data_year:
        digits = [p for p in src.stem.replace("_", "-").split("-") if p.isdigit()]
        data_year = next((d for d in reversed(digits) if len(d) == 4), "")

    db.init_db()
    kept = skipped = 0

    with src.open(newline="", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in ("UNITID", "INSTNM", "CURROPER", "PREDDEG")
                   if c not in (reader.fieldnames or [])]
        if missing:
            echo(f"  That CSV is missing {', '.join(missing)}.")
            echo("  It does not look like the institution-level Scorecard file.")
            return -1

        with db.get_session() as s:
            # One query for the ids already present, so a re-import updates in
            # place instead of doubling the table. A select of one column
            # yields plain scalars.
            existing: set[int] = set(s.exec(select(College.unitid)).all())

            for row in reader:
                if not wanted(row):
                    skipped += 1
                    continue
                college = to_college(row, data_year)
                if not college.unitid:
                    skipped += 1
                    continue
                if college.unitid in existing:
                    old = s.exec(select(College).where(
                        College.unitid == college.unitid)).first()
                    if old:
                        for f in College.model_fields:
                            if f != "id":
                                setattr(old, f, getattr(college, f))
                        s.add(old)
                else:
                    s.add(college)
                    existing.add(college.unitid)
                kept += 1
                if kept % 500 == 0:
                    s.commit()
                    echo(f"      {kept} colleges…")
            s.commit()
            total = len(set(s.exec(select(College.unitid)).all()))

    echo(f"  Imported {kept} colleges ({skipped} rows skipped as not "
         f"bachelor's-degree institutions).")
    echo(f"  The catalogue now holds {total}.")
    return total


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    return 0 if run(sys.argv[1]) >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
