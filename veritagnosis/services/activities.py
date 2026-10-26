
from __future__ import annotations

import dataclasses
import json
import re

LEADERSHIP = [
    "president", "vice president", "vp", "captain", "co-captain", "founder",
    "co-founder", "founded", "leader", "lead", "head", "chair", "chairman",
    "chairwoman", "chairperson", "director", "editor", "editor-in-chief",
    "manager", "organizer", "organiser", "officer", "treasurer", "secretary",
    "coordinator", "mentor", "tutor", "coach", "instructor", "drum major",
    "section leader", "concertmaster", "principal", "representative", "rep",
]

ORGANIZED = [
    "club", "team", "society", "council", "organization", "organisation",
    "association", "league", "band", "orchestra", "choir", "chorus",
    "ensemble", "troupe", "chapter", "crew", "squad", "committee", "nhs",
    "honor society", "student government", "model un", "mun", "debate",
    "robotics", "scouts", "eagle scout", "girl scouts", "boy scouts", "jrotc",
    "newspaper", "yearbook", "theater", "theatre", "fbla", "deca", "hosa",
    "key club", "science olympiad", "mathletes",
]

COMMITTED = [
    "varsity", "intensive", "internship", "intern", "research", "researcher",
    "lab", "job", "work", "worked", "working", "employee", "employed",
    "part-time", "part time", "volunteer", "volunteering", "volunteered",
    "nonprofit", "non-profit", "startup", "business", "competition",
    "competitive", "olympiad", "all-state", "all state", "state champion",
    "state finalist", "state qualifier", "national", "regional", "published", "award", "championship", "certified",
    "apprentice", "apprenticeship", "caregiver", "caretaker",
]

LOW_COMMITMENT = [
    "casual", "casually", "occasional", "occasionally", "sometimes",
    "for fun", "just for fun", "now and then", "watching", "scrolling",
    "browsing", "binge", "binging", "tried", "trying out",
]


def _pattern(words: list[str]) -> re.Pattern:
    alts = sorted((re.escape(w) for w in words), key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(alts) + r")(?![a-z0-9])", re.I)


_LEAD = _pattern(LEADERSHIP)
_ORG = _pattern(ORGANIZED)
_COMMIT = _pattern(COMMITTED)
_LOW = _pattern(LOW_COMMITMENT)

INTENSITY_POINTS = {"light": 6, "moderate": 10, "intense": 15}
YEAR_POINTS = 3          # per year after the first
YEAR_CAP = 12
LEADERSHIP_POINTS = 10
ORGANIZED_POINTS = 4
COMMITTED_POINTS = 5
LOW_POINTS = -6
ACTIVITY_CAP = 40

# How much each activity counts, strongest first. Depth over breadth.
WEIGHTS = (1.0, 0.8, 0.6, 0.4)
LATER_WEIGHT = 0.15
FULL_MARKS = 90          # a weighted total this high is 100
SPREAD_THIN_PENALTY = 8


@dataclasses.dataclass
class Scored:
    name: str
    points: int
    signals: list[str]      # what counted, in words, e.g. "leadership +10"
    leadership: bool
    light: bool


def _years(value) -> int:
    try:
        return max(1, min(6, int(str(value).strip())))
    except (TypeError, ValueError):
        return 1


def score_one(row: dict) -> Scored:
    """Points for one activity, and the reasons, from its own fields only."""
    name = str(row.get("name", "") or "").strip()
    intensity = str(row.get("intensity", "moderate") or "moderate").lower()
    if intensity not in INTENSITY_POINTS:
        intensity = "moderate"
    if _pattern(["intensive", "intense"]).search(name):
        intensity = "intense"
    years = _years(row.get("years", 1))
    starred = str(row.get("leadership", "")).lower() in ("yes", "true", "1")

    signals: list[str] = []
    pts = INTENSITY_POINTS[intensity]
    signals.append(f"{intensity} +{INTENSITY_POINTS[intensity]}")

    yb = min(YEAR_CAP, YEAR_POINTS * (years - 1))
    if yb:
        pts += yb
        signals.append(f"{years} years +{yb}")

    lead_word = _LEAD.search(name)
    leadership = starred or bool(lead_word)
    if leadership:
        pts += LEADERSHIP_POINTS
        why = "leadership" if starred else f"“{lead_word.group(0)}”"
        signals.append(f"{why} +{LEADERSHIP_POINTS}")

    org = _ORG.search(name)
    if org:
        pts += ORGANIZED_POINTS
        signals.append(f"“{org.group(0)}” +{ORGANIZED_POINTS}")

    commit = _COMMIT.search(name)
    if commit:
        pts += COMMITTED_POINTS
        signals.append(f"“{commit.group(0)}” +{COMMITTED_POINTS}")

    low = _LOW.search(name)
    if low:
        pts += LOW_POINTS
        signals.append(f"“{low.group(0)}” {LOW_POINTS}")

    pts = max(0, min(ACTIVITY_CAP, pts))
    return Scored(name=name, points=pts, signals=signals,
                  leadership=leadership, light=intensity == "light")


def parse(profile_data: str | None) -> list[dict]:
    """The activity rows out of the profile's JSON blob. Never raises."""
    if not profile_data:
        return []
    try:
        p = json.loads(profile_data)
    except (TypeError, ValueError):
        return []
    rows = p.get("extracurriculars") if isinstance(p, dict) else None
    return [r for r in (rows or []) if isinstance(r, dict) and str(r.get("name", "")).strip()]


def spread_thin(scored: list[Scored]) -> bool:
    """Six or more activities, most of them light, none led."""
    if len(scored) < 6:
        return False
    light = sum(1 for a in scored if a.light)
    return light * 2 > len(scored) and not any(a.leadership for a in scored)


def score(rows: list[dict]) -> int:
    """0-100 for the whole list."""
    scored = sorted((score_one(r) for r in rows), key=lambda a: -a.points)
    if not scored:
        return 0
    total = 0.0
    for i, a in enumerate(scored):
        w = WEIGHTS[i] if i < len(WEIGHTS) else LATER_WEIGHT
        total += w * a.points
    if spread_thin(scored):
        total -= SPREAD_THIN_PENALTY
    return int(max(0, min(100, round(100 * total / FULL_MARKS))))


def explain(rows: list[dict]) -> str:
    """One or two plain sentences about what the score is built on."""
    scored = sorted((score_one(r) for r in rows), key=lambda a: -a.points)
    if not scored:
        return ("You haven't added any activities yet. Add clubs, sports, jobs, "
                "volunteering or anything else you put real time into.")
    n = len(scored)
    led = sum(1 for a in scored if a.leadership)
    parts = [f"You have {n} {'activity' if n == 1 else 'activities'}, and your "
             f"strongest is {scored[0].name}."]
    if spread_thin(scored):
        parts.append("Most are light with no leadership, which reads as spread "
                     "thin. Going deeper in two or three helps more than adding "
                     "another.")
    elif led == 0:
        parts.append("Star any you lead or help run. Leadership counts for a lot.")
    else:
        parts.append(f"You lead {'one' if led == 1 else led} of them.")
    return " ".join(parts)


def tip(rows: list[dict]) -> str:
    """The single most useful next step for this dimension."""
    scored = [score_one(r) for r in rows]
    if not scored:
        return "Add your activities on your profile"
    if spread_thin(scored):
        return "Pick your two or three main activities and go deeper in them"
    if not any(a.leadership for a in scored):
        return "Star the activities where you lead or help run things"
    return "Add the years and intensity for each activity"
