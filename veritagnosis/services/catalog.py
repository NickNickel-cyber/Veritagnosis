"""
The college catalogue: looking colleges up, and searching for them.

Two sources, deliberately
-------------------------
`content/colleges.py` holds about two dozen colleges read by hand out of each
institution's own Common Data Set. Those numbers are as good as published
admissions data gets, and each entry names the PDF it came from.

That does not scale to the whole country, and a student's real list is mostly
not in those two dozen. So every institution in the federal College Scorecard
is imported into the `college` table (see scripts/import_colleges.py), and this
module is the one place that knows about both.

The rule is simple and always the same: **a curated entry wins.** A number read
out of the institution's own CDS beats the same number averaged into a federal
release a year later, so when both exist the curated one is returned and the
Scorecard row is not consulted. Scorecard rows carry `confidence="medium"` and
a real Scorecard URL, so a screen can still say where a number came from —
which is the promise the curated file was built on and this must not break.

Nothing in here invents a number. A field that neither source publishes comes
back as None, and the screens already know how to render that.
"""

from __future__ import annotations

from sqlmodel import Session, func, or_, select

from veritagnosis.content.colleges import BY_NAME, COLLEGES
from veritagnosis.models import College


def _norm(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def lookup(session: Session | None, name: str) -> dict | None:
    """One college by name, curated first. None when neither source has it."""
    key = _norm(name)
    if not key:
        return None

    curated = BY_NAME.get(key)
    if curated is not None:
        return curated
    if session is None:
        return None

    row = session.exec(
        select(College).where(College.name_key == key)).first()
    return row.as_dict() if row else None


def search(session: Session | None, query: str, limit: int = 12) -> list[dict]:
    """Colleges whose name matches, for the add-a-school box.

    Ordered so the useful answer is first: names that *start* with what was
    typed, then names that merely contain it, then by undergraduate size —
    because a student typing "michigan" means Ann Arbor, and a list that put
    Michigan School of Psychology above it would be technically correct and
    practically useless.
    """
    q = _norm(query)
    if len(q) < 2:
        return []

    out: list[dict] = []
    seen: set[str] = set()

    # Curated first, same rule as lookup().
    for c in COLLEGES:
        k = _norm(c["name"])
        if q in k:
            out.append(c)
            seen.add(k)

    def rank(c: dict) -> tuple:
        k = _norm(c["name"])
        return (0 if k.startswith(q) else 1, -(c.get("size") or 0), k)

    out.sort(key=rank)
    if session is None or len(out) >= limit:
        return out[:limit]

    rows = session.exec(
        select(College)
        .where(College.name_key.contains(q))
        .order_by(College.size.desc().nullslast())
        .limit(limit * 3)
    ).all()

    extra = [r.as_dict() for r in rows if r.name_key not in seen]
    extra.sort(key=rank)
    return (out + extra)[:limit]


def count(session: Session | None) -> int:
    """How many colleges are known. Curated entries are counted once."""
    n = len(COLLEGES)
    if session is None:
        return n
    imported = session.exec(select(func.count()).select_from(College)).one()
    if isinstance(imported, tuple):
        imported = imported[0]
        
    curated_also_imported = session.exec(
        select(func.count()).select_from(College)
        .where(College.name_key.in_([_norm(c["name"]) for c in COLLEGES]))
    ).one()
    if isinstance(curated_also_imported, tuple):
        curated_also_imported = curated_also_imported[0]
    return n + int(imported) - int(curated_also_imported)


def is_imported(session: Session | None) -> bool:
    """Whether the Scorecard import has been run."""
    if session is None:
        return False
    row = session.exec(select(College.id).limit(1)).first()
    return row is not None
