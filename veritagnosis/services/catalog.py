
from __future__ import annotations

import dataclasses
import re

from sqlmodel import Session, func, or_, select

from veritagnosis.content.colleges import ALIASES, BY_NAME, COLLEGES
from veritagnosis.models import College, School


def _norm(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def loose(name: str) -> str:
    s = (name or "").lower().replace("&", " and ").replace("’", "'")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    s = re.sub(r"^the ", "", s)
    return " ".join(s.split())


_ALIAS = {loose(k): v for k, v in ALIASES.items()}


def official_name(name: str) -> str:
    """The full official name for a nickname, or the name itself."""
    return _ALIAS.get(loose(name), (name or "").strip())


_CURATED: dict[str, dict] = {}
for _c in COLLEGES:
    _CURATED[loose(_c["name"])] = _c
    _CURATED[loose(official_name(_c["name"]))] = _c


_INDEX: dict = {"sig": None, "names": {}, "rows": []}


def _index(session: Session) -> dict:
    n = session.exec(select(func.count()).select_from(College)).one()
    n = n[0] if isinstance(n, tuple) else n
    sig = (str(session.get_bind().url), int(n))
    if _INDEX["sig"] != sig:
        rows = session.exec(select(College.name, College.state, College.size)).all()
        _INDEX["names"] = {loose(r[0]): r[0] for r in rows}
        _INDEX["rows"] = [(loose(r[0]), r[0], r[1] or "", r[2] or 0) for r in rows]
        _INDEX["sig"] = sig
    return _INDEX


@dataclasses.dataclass
class Match:
    """A college the catalogue recognised, and the full name to save it as."""

    name: str
    entry: dict


def resolve(session: Session | None, text: str) -> Match | None:
    official = official_name(text)
    key = loose(official)
    if not key:
        return None

    idx = _index(session) if session is not None else None
    full = idx["names"].get(key) if idx else None

    curated = _CURATED.get(key)
    if curated is not None:
        return Match(full or official, curated)
    if not full:
        return None
    row = session.exec(select(College).where(College.name == full)).first()
    return Match(full, row.as_dict()) if row else None


def lookup(session: Session | None, name: str) -> dict | None:
    """One college by name, curated first. None when neither source has it."""
    m = resolve(session, name)
    return m.entry if m else None


def suggest(session: Session | None, text: str, limit: int = 6) -> list[dict]:
    q = loose(text)
    if len(q) < 2:
        return []

    picked: list[tuple] = []          # (rank, -size, name, state)
    seen: set[str] = set()

    def add(rank: int, name: str, state: str, size: int) -> None:
        k = loose(name)
        if k and k not in seen:
            seen.add(k)
            picked.append((rank, -size, name, state))

    idx = _index(session) if session is not None else None

    # A nickname, typed whole or in part ("umi" for UMich).
    for alias, full in _ALIAS.items():
        if alias == q or (len(q) >= 3 and alias.startswith(q)):
            name = (idx["names"].get(loose(full)) if idx else None)
            if name is None and loose(full) in _CURATED:
                name = full
            if name is None:
                continue      # not in this catalogue: offering it would loop
            add(0 if alias == q else 1, name, "", 0)

    if idx:
        for k, name, state, size in idx["rows"]:
            if k.startswith(q):
                add(2, name, state, size)
            elif q in k:
                add(3, name, state, size)
    else:
        for c in COLLEGES:
            full = official_name(c["name"])
            k = loose(full)
            if k.startswith(q) or q in k or q in loose(c["name"]):
                add(2 if k.startswith(q) else 3, full, c.get("state", ""), 0)

    picked.sort()
    out = []
    for _, _, name, state in picked[:limit]:
        if not state and idx:
            # A nickname row: look its state up now that the full name is known.
            state = next((r[2] for r in idx["rows"] if r[1] == name), "")
        out.append({"name": name, "state": state})
    return out


def tidy_names(session: Session, user_id: int) -> int:
    changed = 0
    for school in session.exec(select(School).where(School.user_id == user_id)).all():
        m = resolve(session, school.name or "")
        if m and m.name and m.name != school.name:
            school.name = m.name[:120]
            session.add(school)
            changed += 1
    if changed:
        session.commit()
    return changed


def search(session: Session | None, query: str, limit: int = 12) -> list[dict]:
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
