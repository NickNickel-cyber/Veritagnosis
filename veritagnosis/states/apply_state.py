"""
The application screens: the school list, the essay coach,
and recommenders.

Merged from: schools_state, essay_state, recs_state.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
import reflex as rx
from sqlmodel import select
from veritagnosis import db
from veritagnosis.content.aid import ROUNDS as ROUND_NAMES
from veritagnosis.models import AppStatus, Recommender, School, Tier, utcnow
from veritagnosis.services import wellbeing as achievements, apply as progress
from veritagnosis.services import catalog
from veritagnosis.states.base import FeatureState
from veritagnosis.content import copy as promptlib
from veritagnosis.content.copy import DONE, STEPS
from veritagnosis.models import Essay, EssayVersion, School, utcnow
from veritagnosis.services import wellbeing as achievements, prose
from datetime import datetime, timedelta, timezone
from veritagnosis.content import copy as asking
from veritagnosis.models import Recommender, School, User, utcnow


# ====================================================================
# schools_state
# ====================================================================

@dataclasses.dataclass
class Step:
    """One line of a school's checklist."""

    key: str
    label: str
    done: bool
    detail: str
    hint: str
    route: str
    weight: int


@dataclasses.dataclass
class SchoolRow:
    id: int
    name: str
    tier: str
    status: str
    status_key: str
    progress: int
    deadline: str          # "Jan 01" for display
    deadline_iso: str      # "2027-01-01" for the date input
    when: str              # "12 days", "Tomorrow", "No deadline set"
    urgency: str           # none | later | soon | urgent | passed | done
    notes: str
    essays_required: int
    recs_required: int
    next_label: str
    next_hint: str
    next_route: str
    steps: list[Step]
    ring_dash: str         # stroke-dashoffset for the progress ring
    round_name: str        # Early Decision, Regular Decision, ...
    binding: bool          # ED commits you before you can compare aid
    letters: str           # "2 of 2 letters" — counts only teachers who agreed


STATUS_LABEL = {
    "not_started": "Not started", "in_progress": "In progress",
    "submitted": "Submitted", "accepted": "Accepted",
    "rejected": "Rejected", "waitlisted": "Waitlisted",
}
STATUS_ORDER = ["not_started", "in_progress", "submitted",
                "accepted", "waitlisted", "rejected"]

# Circumference of the r=26 ring drawn in the page.
RING_C = 163.36


class SchoolsState(FeatureState, rx.State):
    safety: list[SchoolRow] = []
    target: list[SchoolRow] = []
    reach: list[SchoolRow] = []

    open_id: int = 0          # which school's checklist is expanded
    sort_by: str = "deadline"  # deadline | progress | name
    new_name: str = ""
    new_tier: str = "target"

    # headline numbers
    total: int = 0
    average: int = 0
    submitted: int = 0
    urgent: int = 0
    next_name: str = ""
    next_when: str = ""
    next_urgency: str = "none"

    just_earned: str = ""

    # The add box. `query` is what is typed; `suggestions` are full official
    # names matching it, so the student picks a name the catalogue knows.
    query: str = ""
    suggestions: list[dict[str, str]] = []
    added_as: str = ""
    add_error: str = ""

    @rx.var
    def has_schools(self) -> bool:
        return self.total > 0

    @rx.var(deps=["average"])
    def average_dash(self) -> str:
        return str(round(RING_C * (1 - self.average / 100), 1))

    @rx.var(deps=["next_name", "next_when"])
    def next_line(self) -> str:
        if not self.next_name:
            return "No deadlines recorded yet."
        return f"{self.next_name} is next — {self.next_when}"
    # ---------------------------------------------------------------- load
    @rx.event
    async def load(self):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        self._refresh(uid)
        self.loading = False

    def _refresh(self, uid: int) -> None:
        with db.get_session() as s:
            # Recompute every ring from the real work before drawing anything.
            progress.recompute_all(s, uid)

            rows = list(s.exec(select(School).where(School.user_id == uid)).all())
            recs = list(s.exec(select(Recommender)
                               .where(Recommender.user_id == uid)).all())
            packed = [self._pack(s, uid, r, recs) for r in rows]

            stats = achievements.gather(s, uid)
            new = achievements.award(s, uid, stats)
            self.just_earned = new[0]["title"] if new else ""

            summary = progress.summary(s, uid)

        key = {
            "deadline": lambda r: (r.deadline_iso == "", r.deadline_iso, r.name.lower()),
            "progress": lambda r: (-r.progress, r.name.lower()),
            "name": lambda r: r.name.lower(),
        }[self.sort_by]
        packed.sort(key=key)

        self.safety = [r for r in packed if r.tier == "safety"]
        self.target = [r for r in packed if r.tier == "target"]
        self.reach = [r for r in packed if r.tier == "reach"]

        self.total = summary["count"]
        self.average = summary["average"]
        self.submitted = summary["submitted"]
        self.urgent = summary["urgent"]
        self.next_name = summary["next_name"]
        self.next_when = summary["next_when"]
        self.next_urgency = summary["next_urgency"]

    def _pack(self, session, uid: int, r: School, recs=None) -> SchoolRow:
        ms = progress.milestones(session, uid, r)
        nxt = progress.next_step(ms)
        pct = progress.percent(ms)
        need = r.recs_required or 0
        got = 0
        for rec in (recs or []):
            if rec.status not in ("agreed", "submitted"):
                continue
            ids = _ids(rec.school_ids)
            # No colleges named means a general letter, which really does go
            # to all of them.
            if not ids or r.id in ids:
                got += 1

        return SchoolRow(
            id=r.id, name=r.name, tier=r.tier.value,
            status=STATUS_LABEL.get(r.status.value, r.status.value),
            status_key=r.status.value,
            progress=pct,
            deadline=r.deadline.strftime("%b %d") if r.deadline else "",
            deadline_iso=r.deadline.strftime("%Y-%m-%d") if r.deadline else "",
            when=progress.deadline_phrase(r),
            urgency=progress.urgency(r),
            notes=r.notes or "",
            essays_required=r.essays_required or 1,
            recs_required=r.recs_required or 0,
            next_label=nxt.label if nxt else "Everything done",
            next_hint=nxt.hint if nxt else "Nothing left to do here.",
            next_route=nxt.route if nxt else "/applications",
            steps=[Step(key=m.key, label=m.label, done=m.done, detail=m.detail,
                        hint=m.hint, route=m.route, weight=m.weight) for m in ms],
            ring_dash=str(round(RING_C * (1 - pct / 100), 1)),
            round_name=ROUND_NAMES.get(r.round or "regular", "Regular Decision"),
            binding=(r.round or "regular") in ("ed", "ed2"),
            letters=(f"{got} of {need} letters" if need else "no letters needed"),
        )

    # -------------------------------------------------------------- editing
    @rx.event
    async def add_school(self, form: dict):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        name = (form.get("name") or self.query or "").strip()
        if not name:
            self.add_error = "Type the college's full name first."
            return
        tier = form.get("tier") or "target"
        if tier not in Tier._value2member_map_:
            tier = "target"
        with db.get_session() as s:
            match = catalog.resolve(s, name)
            if match is None and catalog.is_imported(s):
                # Not a name the catalogue knows. Saving it anyway is how a
                # list ends up with "UMich" and no data behind it.
                options = catalog.suggest(s, name, 6)
                self.suggestions = options
                self.added_as = ""
                self.add_error = (
                    f"“{name}” isn't a full college name. Pick the one you "
                    f"mean below." if options else
                    f"No college called “{name}” was found. Type its full "
                    f"name, like “University of Michigan-Ann Arbor”.")
                return
            full = match.name if match else name
            mine = s.exec(select(School).where(School.user_id == uid)).all()
            if any(catalog.loose(x.name) == catalog.loose(full) for x in mine):
                self.add_error = f"{full} is already on your list."
                self.suggestions = []
                return
            s.add(School(user_id=uid, name=full[:120], tier=Tier(tier)))
            s.commit()
        self.add_error = ""
        self.query = ""
        self.suggestions = []
        self.added_as = (f"Added as “{full}”."
                         if catalog.loose(full) != catalog.loose(name) else "")
        self._refresh(uid)

    @rx.event
    def set_query(self, value: str):
        """Typing in the add box: offer full names as the student types."""
        self.query = value
        self.add_error = ""
        self.added_as = ""
        if len(catalog.loose(value)) < 2:
            self.suggestions = []
            return
        with db.get_session() as s:
            self.suggestions = catalog.suggest(s, value, 6)

    @rx.event
    def pick(self, name: str):
        """Fill the box with a suggested full name."""
        self.query = name
        self.suggestions = []
        self.add_error = ""

    @rx.event
    def toggle_open(self, school_id: int):
        self.open_id = 0 if self.open_id == school_id else school_id

    @rx.event
    async def set_sort(self, how: str):
        self.sort_by = how if how in ("deadline", "progress", "name") else "deadline"
        uid = await self._user_id()
        if uid is not None:
            self._refresh(uid)

    @rx.event
    async def set_deadline(self, school_id: int, value: str):
        """From a date input, so the value is always YYYY-MM-DD or empty."""
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        when = None
        if value:
            try:
                when = datetime.strptime(value, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc)
            except ValueError:
                self.error = "That date didn't make sense."
                return
        with db.get_session() as s:
            row = s.get(School, school_id)
            if row and row.user_id == uid:      # never trust an id from the client
                row.deadline = when
                s.add(row); s.commit()
        self.error = ""
        self._refresh(uid)

    @rx.event
    async def set_notes(self, school_id: int, value: str):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        with db.get_session() as s:
            row = s.get(School, school_id)
            if row and row.user_id == uid:
                row.notes = value[:4000]
                s.add(row); s.commit()
        self._refresh(uid)

    @rx.event
    async def set_tier(self, school_id: int, tier: str):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        if tier not in ("safety", "target", "reach"):
            return
        with db.get_session() as s:
            row = s.get(School, school_id)
            if row and row.user_id == uid:
                row.tier = Tier(tier)
                s.add(row); s.commit()
        self._refresh(uid)

    @rx.event
    async def set_status(self, school_id: int, status: str):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        if status not in STATUS_ORDER:
            return
        with db.get_session() as s:
            row = s.get(School, school_id)
            if row and row.user_id == uid:
                row.status = AppStatus(status)
                if status == "submitted" and row.submitted_at is None:
                    row.submitted_at = utcnow()
                s.add(row); s.commit()
        self._refresh(uid)

    @rx.event
    async def set_requirement(self, school_id: int, field: str, value: str):
        """How many essays or letters this college asks for."""
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        try:
            n = max(0, min(10, int(value or 0)))
        except (TypeError, ValueError):
            return
        with db.get_session() as s:
            row = s.get(School, school_id)
            if row and row.user_id == uid:
                if field == "essays":
                    row.essays_required = n
                elif field == "recs":
                    row.recs_required = n
                s.add(row); s.commit()
        self._refresh(uid)

    @rx.event
    async def remove(self, school_id: int):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        with db.get_session() as s:
            row = s.get(School, school_id)
            if row and row.user_id == uid:
                s.delete(row); s.commit()
        if self.open_id == school_id:
            self.open_id = 0
        self._refresh(uid)

    @rx.event
    def dismiss_earned(self):
        self.just_earned = ""


# ====================================================================
# essay_state
# ====================================================================

MAX_SHOWN = 14

# Keep this many snapshots. Enough to get back a paragraph deleted last week,
# few enough that the list stays readable.
MAX_VERSIONS = 12

KIND_META = {
    "confusable": ("Wrong word", "high"),
    "spacing":    ("Spacing", "low"),
    "cliche":     ("Overused", "high"),
    "telling":    ("Show, don't tell", "high"),
    "hedge":      ("Hedging", "high"),
    "vague_qty":  ("How many?", "med"),
    "wordy":      ("Wordy", "med"),
    "filler":     ("Filler", "med"),
    "expletive":  ("Slow start", "med"),
    "passive":    ("Passive", "med"),
    "long":       ("Long sentence", "high"),
    "rhythm":     ("Rhythm", "high"),
    "echo":       ("Repeat", "med"),
    "adverb":     ("Adverb", "low"),
    "weak":       ("Vague", "low"),
}


@dataclasses.dataclass
class Issue:
    """One problem, flattened for the browser. The precise offsets stay on the
    server where they cannot be tampered with."""

    idx: int
    kind: str
    label: str
    why: str
    original: str
    fix: str
    severity: str
    auto: bool
    has_fix: bool
    action: str


@dataclasses.dataclass
class Chunk:
    text: str
    kind: str
    idx: int
    marked: bool


@dataclasses.dataclass
class Cat:
    key: str
    name: str
    count: int
    severity: str


@dataclasses.dataclass
class Para:
    """One paragraph, for the outline."""

    n: int
    opening: str
    words: int
    percent: int
    tone: str       # short | ok | long


@dataclasses.dataclass
class VersionRow:
    id: int
    label: str
    when: str
    words: int
    score: int
    delta: str      # "+120 words" against the version before it


@dataclasses.dataclass
class PromptRow:
    """One prompt in the chooser.

    `short` used to be the only thing rendered — the first 78 characters of a
    prompt, followed by an ellipsis. A student cannot choose between eleven
    essay prompts by reading the first 78 characters of each, which is most of
    why the old picker was useless as well as ugly. The full text and the
    coaching note are both carried now, and the chooser shows them.
    """

    key: str
    text: str
    note: str
    words: int
    short: str
    picked: bool
    group: str      # "Common App" | "Supplemental"


@dataclasses.dataclass
class Dim:
    """One of the five things the score is made of."""

    key: str
    name: str
    value: int
    note: str
    weight: str     # "28%" — so the student can see what is being weighted
    tone: str       # weak | fair | good


@dataclasses.dataclass
class StoryStep:
    """One move of the five-move shape, present or missing."""

    key: str
    name: str
    note: str
    present: bool
    strength: int
    para: str       # "¶3" or "" when missing
    state: str      # missing | thin | there


@dataclasses.dataclass
class JourneyPoint:
    """One dot on the draft journey."""

    id: int
    when: str
    label: str
    words: int
    score: int
    height: int     # bar height as a percentage, for the chart
    delta: str
    current: bool
    scored: bool


class EssayState(FeatureState, rx.State):
    essay_id: int = 0
    prompt: str = ""
    prompt_note: str = ""
    body: str = ""
    step: int = 0
    done: bool = False
    reaction: str = ""
    school_options: list[str] = []
    word_target: int = 650

    # ---- analysis -------------------------------------------------------
    issues: list[Issue] = []
    cats: list[Cat] = []
    chunks: list[Chunk] = []
    paras: list[Para] = []
    score: int = 0
    band: str = ""
    strengths: list[str] = []
    rhythm_note: str = ""
    grade_note: str = ""
    total_issues: int = 0
    high_issues: int = 0
    auto_count: int = 0
    analysed_len: int = -1

    stat_words: int = 0
    stat_sentences: int = 0
    stat_avg: str = "0"
    stat_read: str = "0 sec"
    stat_variety: int = 0

    # ---- interface ------------------------------------------------------
    review_mode: bool = False
    outline_mode: bool = False
    show_prompts: bool = False
    show_versions: bool = False
    focus: str = ""
    open_issue: int = -1
    flash: str = ""
    last_applied: str = ""
    dirty: bool = False
    saved_at: str = ""
    just_earned: str = ""

    versions: list[VersionRow] = []

    # ---- the coach panel -------------------------------------------------
    coach_tab: str = "overview"
    coach_open: bool = False      # the drawer, on a narrow screen

    # ---- scoring readiness ----------------------------------------------
    #
    # `score_ready` is the flag the screen branches on. Until it is true there
    # is no number anywhere on the page — not greyed out, not a zero, nothing.
    # A score invented from forty words is the thing that made the old screen
    # feel fake, and the fix is not a smaller number, it is no number.
    score_ready: bool = False
    score_provisional: bool = False
    score_stage: str = "blank"
    score_confidence: int = 0
    words_needed: int = 0
    dims: list[Dim] = []
    story: list[StoryStep] = []
    story_done: int = 0

    # ---- next best edit --------------------------------------------------
    nbe_kind: str = "write"
    nbe_title: str = ""
    nbe_why: str = ""
    nbe_how: str = ""
    nbe_gain: str = ""
    nbe_idx: int = -1

    journey: list[JourneyPoint] = []

    # The cursor fix.
    #
    # The writing box used to be a *controlled* input: the server held the text
    # and pushed it back on every keystroke. React then re-set the box's value,
    # and re-setting a textarea's value puts the caret at the end — so clicking
    # into the middle of a word to fix a typo threw you to the bottom of the
    # essay on the very next character.
    #
    # Now the browser owns the text while you type. This number is the box's
    # React key, so bumping it rebuilds the box with new text. It is bumped
    # ONLY when the app deliberately changes the draft — loading, applying a
    # fix, polishing, undoing, restoring. Never while typing.
    doc_version: int = 0

    # Backend-only: never leaves the server.
    _findings: list = []
    _undo_body: str = ""
    _undo_label: str = ""

    REACTIONS: dict[str, str] = {
        "idea": ("Write it down now, even if it's messy, before you lose it. You can "
                 "clean it up later."),
        "love": "Keep that part. Whatever you liked about it, do more of that.",
        "fire": "Nice, keep going. Finish the thought before you edit anything.",
        "stuck": ("Getting stuck is normal. Try writing a bad version of the next "
                  "sentence on purpose. It usually gets you moving again."),
    }

    # ------------------------------------------------------------ the coach
    @rx.var(deps=["score", "stat_words", "high_issues", "last_applied", "dirty"])
    def coach_mood(self) -> str:
        """What the character on screen is doing.

        Tied to the state of the draft rather than picked at random, so the
        figure is feedback and not decoration: it looks pleased when the writing
        gets better and concerned when there is a lot to fix.
        """
        if self.stat_words < 5:
            return "sleepy"
        if self.last_applied:
            return "cheer"
        if not self.score_ready:
            return "writing" if self.dirty else "idle"
        if self.score >= 80:
            return "proud"
        if self.high_issues >= 6:
            return "worried"
        if self.dirty:
            return "writing"
        return "idle"

    @rx.var
    def coach_says(self) -> str:
        if self.reaction and self.reaction in self.REACTIONS:
            return self.REACTIONS[self.reaction]
        return DONE["say"] if self.done else STEPS[min(self.step, len(STEPS) - 1)]["say"]

    @rx.var
    def coach_hint(self) -> str:
        if self.reaction and self.reaction in self.REACTIONS:
            return "Tap the same button again to go back to the step."
        return DONE["hint"] if self.done else STEPS[min(self.step, len(STEPS) - 1)]["hint"]

    # ------------------------------------------------------------- numbers
    @rx.var
    def words(self) -> int:
        return len([w for w in self.body.split() if w.strip()])

    @rx.var
    def step_of(self) -> str:
        # "Tip", not "Step". These six are writing advice, and calling them
        # steps implied a process you could be behind on.
        return f"Tip {min(self.step + 1, len(STEPS))} of {len(STEPS)}"

    @rx.var(deps=["stat_words", "word_target"])
    def target_percent(self) -> int:
        if not self.word_target:
            return 0
        return min(100, int(round(100 * self.stat_words / self.word_target)))

    @rx.var(deps=["stat_words", "word_target"])
    def target_line(self) -> str:
        left = self.word_target - self.stat_words
        if self.stat_words == 0:
            return f"{self.word_target}-word limit"
        if left > 0:
            return f"{left} words left"
        if left == 0:
            return "Exactly on the limit"
        return f"{abs(left)} words over. You'll need to cut some."

    @rx.var(deps=["stat_words", "word_target"])
    def over_limit(self) -> bool:
        return self.stat_words > self.word_target

    @rx.var
    def has_undo(self) -> bool:
        return bool(self._undo_body) or self._undo_label != ""

    @rx.var
    def can_polish(self) -> bool:
        return self.auto_count > 0

    @rx.var(deps=["dirty", "saved_at"])
    def save_line(self) -> str:
        if self.dirty:
            return "Unsaved changes"
        return f"Saved {self.saved_at}" if self.saved_at else "Saved"

    @rx.var(deps=["score", "band", "score_ready", "score_provisional"])
    def score_line(self) -> str:
        if not self.score_ready:
            return ""
        if self.score_provisional:
            return (("Early score. It'll change a lot as you write, so focus on the shape "
                     "for now."))
        return {
            "sharp": "This is in good shape. Read it out loud once more and you're done.",
            "solid": "Solid draft. What's left below is polish.",
            "getting there": "The structure is there. Fix the red items first.",
            "rough draft": "Normal for a draft. Nothing here is hard to fix.",
            "early days": "It's early, and that's fine.",
        }.get(self.band, "")

    @rx.var(deps=["auto_count"])
    def polish_label(self) -> str:
        return (f"Fix {self.auto_count} automatically"
                if self.auto_count else "Nothing to auto-fix")

    @rx.var
    def prompt_list(self) -> list[PromptRow]:
        common = {p["key"] for p in promptlib.COMMON_APP}
        return [
            PromptRow(key=p["key"], text=p["text"], note=p["note"],
                      words=p["words"],
                      short=(p["text"][:78] + "…") if len(p["text"]) > 78 else p["text"],
                      picked=self.prompt.strip() == p["text"],
                      group="Common App" if p["key"] in common else "Supplemental")
            for p in promptlib.ALL
        ]

    @rx.var(deps=["prompt"])
    def prompt_words_hint(self) -> str:
        p = promptlib.find(self.prompt)
        return f"{p['words']}-word limit" if p else ""

    # --------------------------------------------------- the coach panel
    @rx.event
    def set_coach_tab(self, key: str):
        self.coach_tab = key
        self.coach_open = True

    @rx.event
    def toggle_coach(self):
        self.coach_open = not self.coach_open

    @rx.var(deps=["score_ready", "words_needed", "stat_words"])
    def gate_line(self) -> str:
        """What the panel says instead of a score."""
        if self.score_ready:
            return ""
        if self.stat_words == 0:
            return (("Nothing here yet. Write a rough first sentence. It doesn't have to "
                     "be good."))
        return (f"Write {self.words_needed} more words and I can give you a real "
                f"score. Anything shorter would just be a guess.")

    @rx.var(deps=["stat_words"])
    def gate_percent(self) -> int:
        if self.stat_words >= prose.WORDS_NO_SCORE:
            return 100
        return int(round(100 * self.stat_words / prose.WORDS_NO_SCORE))

    @rx.var(deps=["score_provisional", "score_confidence"])
    def confidence_line(self) -> str:
        if not self.score_ready:
            return ""
        if self.score_provisional:
            return (f"Early estimate, {self.score_confidence}% confidence. It'll "
                    f"settle as you write more.")
        return f"Full score · {self.score_confidence}% confidence"

    @rx.var(deps=["story_done"])
    def story_line(self) -> str:
        if self.stat_words < 25:
            return "The five moves show up here as you write."
        if self.story_done == 5:
            return "All five moves are in your draft. The hard part is done."
        missing = 5 - self.story_done
        return (f"{self.story_done} of 5 moves are here. Adding the missing "
                f"{'one' if missing == 1 else missing} will help more than all the "
                f"small fixes combined.")

    # ------------------------------------------------------- the analysis
    def _build_dims(self, detail: dict) -> None:
        self.dims = [
            Dim(key=d["key"], name=d["name"], value=d["value"], note=d["note"],
                weight=f"{int(round(d['weight'] * 100))}%",
                tone=("good" if d["value"] >= 70
                      else "fair" if d["value"] >= 45 else "weak"))
            for d in detail.get("dimensions", [])
        ]

    def _build_story(self, smap: list[dict]) -> None:
        out = []
        done = 0
        for s in smap:
            if s["strength"] >= 70:
                state = "there"
            elif s["present"]:
                state = "thin"
            else:
                state = "missing"
            if s["present"]:
                done += 1
            out.append(StoryStep(
                key=s["key"], name=s["name"], note=s["note"],
                present=s["present"], strength=s["strength"],
                para=f"¶{s['para']}" if s["present"] and s["para"] else "",
                state=state))
        self.story = out
        self.story_done = done

    def _build_next_edit(self) -> None:
        """The single highest-leverage thing to do next.

        Ranked by how much it actually changes the essay, which is not the same
        as how easy it is to detect. A missing turn outranks every filler word in
        the draft, and telling a student to delete "very" while their essay has no
        story in it is the kind of advice that makes a tool feel useless.
        """
        # 1. Not enough writing to advise on.
        if self.stat_words < prose.WORDS_NO_SCORE:
            left = max(0, prose.WORDS_NO_SCORE - self.stat_words)
            self.nbe_kind = "write"
            self.nbe_title = ("Just get a first draft down" if self.stat_words < 20
                              else f"Keep going, about {left} more words")
            self.nbe_why = (("There's nothing to edit yet, and editing while you draft makes it "
                             "hard to finish. Feedback will show up once there's a draft to read."))
            self.nbe_how = (("Pick one small, real moment, like an afternoon or a conversation, "
                             "and write what happened in order. Don't stop to fix anything."))
            self.nbe_gain = "Unlocks your full score"
            self.nbe_idx = -1
            return

        # 2. A missing move in the shape. The largest single lever there is.
        missing = [s for s in self.story if s.state == "missing"]
        if missing:
            order = {"change": 0, "reflection": 1, "situation": 2,
                     "stakes": 3, "action": 4}
            s = sorted(missing, key=lambda x: order.get(x.key, 9))[0]
            self.nbe_kind = "story"
            self.nbe_title = {
                "change": "Add the turn",
                "reflection": "Say what you understood afterwards",
                "situation": "Ground it in one place and time",
                "stakes": "Bring it to now",
                "action": "Put yourself in the action",
            }.get(s.key, f"Add the missing {s.name.lower()}")
            self.nbe_why = {
                "change": ("Nothing changes in this draft. Without a turning point it reads like "
                           "a description instead of a story, and readers tend to skim "
                           "descriptions."),
                "reflection": ("You say what happened, but not what you understood afterward. That's "
                               "the part admissions officers care about most."),
                "situation": ("The essay never settles on a specific place or time. Give the reader "
                              "one real scene to stand in."),
                "stakes": ("It ends in the past. Add a line about now so the reader knows it "
                           "stuck with you."),
                "action": ("The essay is about you, but you're not doing much in it. Things "
                           "happen around you instead of because of you."),
            }.get(s.key, s.note)
            self.nbe_how = s.note
            self.nbe_gain = "Biggest improvement you can make"
            self.nbe_idx = -1
            return

        # 3. A dimension well below the rest — a systemic weakness, not a typo.
        if self.dims:
            worst = min(self.dims, key=lambda d: d.value)
            spread = max(d.value for d in self.dims) - worst.value
            if worst.value < 50 and spread >= 22:
                self.nbe_kind = "dimension"
                self.nbe_title = f"{worst.name} is holding the score down"
                self.nbe_why = (f"{worst.note} It's at {worst.value} out of 100 "
                                f"while the rest of the draft is well ahead, so "
                                f"this is where you'll gain the most.")
                self.nbe_how = {
                    "craft": ("Go through the Problems tab, starting with the red ones. Most have a "
                              "one-tap fix."),
                    "concrete": ("Find abstract words like “passion,” “journey” and “growth” and "
                                 "replace them with what actually happened."),
                    "voice": ("Cut the hedging. “I think that maybe” can usually just be “I.” Read "
                              "a paragraph out loud and write it the way you said it."),
                    "rhythm": "Find your longest sentence and break it in two. Then make "
                              "one sentence four words long.",
                    "structure": "Check the Structure tab and build up the weakest move.",
                }.get(worst.key, "See the Problems tab.")
                self.nbe_gain = f"Up to {min(20, int((70 - worst.value) * 0.3))} points"
                self.nbe_idx = -1
                return

        # 4. Otherwise the worst specific thing in the text.
        if self.issues:
            rank = {"high": 0, "med": 1, "low": 2}
            top = sorted(self.issues, key=lambda i: rank.get(i.severity, 1))[0]
            self.nbe_kind = "fix"
            self.nbe_title = f"{top.label}: “{top.original}”"
            self.nbe_why = top.why
            self.nbe_how = (f"Replace it with “{top.fix}”." if top.has_fix and top.fix
                            else "Delete it." if top.has_fix
                            else "Rewrite the sentence around it.")
            self.nbe_gain = "Quick win"
            self.nbe_idx = top.idx
            return

        # 5. Nothing left to say.
        self.nbe_kind = "done"
        self.nbe_title = "Nothing left to fix"
        self.nbe_why = (("Every check passes and all five moves are there. Anything else is "
                         "your call."))
        self.nbe_how = ("Read it out loud from start to finish. Fix anything you trip over.")
        self.nbe_gain = ""
        self.nbe_idx = -1

    def _build_journey(self) -> None:
        """Saved versions plus where the draft stands now, as a small chart.

        The point is not the individual numbers. It is that a student who has
        been rewriting for three hours can see that it is in fact getting better,
        which is not something you can feel from inside the draft.
        """
        pts: list[JourneyPoint] = []
        rows = list(reversed(self.versions))      # oldest first
        for i, v in enumerate(rows):
            pts.append(JourneyPoint(
                id=v.id, when=v.when, label=f"Save {i + 1}", words=v.words,
                score=v.score, height=max(4, v.score), delta=v.delta,
                current=False, scored=v.score > 0))
        prev = rows[-1].words if rows else 0
        d = self.stat_words - prev
        pts.append(JourneyPoint(
            id=0, when="now", label="Now", words=self.stat_words,
            score=self.score, height=max(4, self.score) if self.score_ready else 4,
            delta=(f"{'+' if d >= 0 else ''}{d} words" if rows else "current draft"),
            current=True, scored=self.score_ready))
        self.journey = pts[-10:]

    # ---------------------------------------------------------------- load
    @rx.event
    async def load(self):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        with db.get_session() as s:
            row = s.exec(select(Essay).where(Essay.user_id == uid)
                         .order_by(Essay.updated_at.desc())).first()
            if row is None:
                row = Essay(user_id=uid,
                            prompt=promptlib.COMMON_APP[0]["text"],
                            word_target=650)
                s.add(row); s.commit(); s.refresh(row)
            self.essay_id = row.id
            self.prompt = row.prompt
            self.body = row.body or ""
            self.step = row.step
            self.done = row.done
            self.reaction = row.reaction or ""
            self.word_target = row.word_target or 650
            self.school_options = [r.name for r in
                                   s.exec(select(School).where(School.user_id == uid)).all()]
            self._load_versions(s, uid)

        p = promptlib.find(self.prompt)
        self.prompt_note = p["note"] if p else ""
        self._analyse()
        self.dirty = False
        self.doc_version += 1      # the draft came from the server: rebuild the box
        self.loading = False

    # ------------------------------------------------------------ analysis
    def _analyse(self) -> None:
        """Read the draft and rebuild everything the screen shows.

        A plain method rather than an event handler: several handlers finish by
        re-reading the draft, and in Reflex an event handler cannot call
        another one.
        """
        text = self.body or ""
        result = prose.analyse(text)
        found = result["findings"]

        detail = result["detail"]

        self._findings = found
        self.score = detail["score"]
        self.band = prose.band(detail["score"])
        self.score_ready = detail["ready"]
        self.score_provisional = detail["provisional"]
        self.score_stage = detail["stage"]
        self.score_confidence = detail["confidence"]
        self.words_needed = detail["needed"]
        self.strengths = result["strengths"]
        self.rhythm_note = result["rhythm_note"]
        self.grade_note = result["grade_note"]
        self.total_issues = len(found)
        self.high_issues = sum(1 for f in found if f.severity == "high")
        self.auto_count = sum(1 for f in found if f.auto and f.has_fix)
        self.analysed_len = len(text)

        st = result["stats"]
        self.stat_words = st["words"]
        self.stat_sentences = st["sentences"]
        self.stat_avg = f"{st['avg_sentence']:.0f}"
        secs = st["reading_seconds"]
        self.stat_read = (f"{secs} sec" if secs < 60
                          else f"{secs // 60} min {secs % 60} sec")
        self.stat_variety = st["rhythm_variety"]

        counts = result["counts"]
        order = {"high": 0, "med": 1, "low": 2}
        self.cats = sorted(
            [Cat(key=k, name=KIND_META.get(k, (k, "med"))[0], count=v,
                 severity=KIND_META.get(k, (k, "med"))[1])
             for k, v in counts.items()],
            key=lambda c: (order[c.severity], -c.count))

        self._build_issues()
        self._build_chunks()
        self._build_outline(text)
        self._build_dims(detail)
        self._build_story(result["story"])
        self._build_next_edit()
        self._build_journey()

    def _build_issues(self) -> None:
        rank = {"high": 0, "med": 1, "low": 2}
        picked = [(i, f) for i, f in enumerate(self._findings)
                  if not self.focus or f.kind == self.focus]
        picked.sort(key=lambda p: (rank.get(p[1].severity, 1), p[1].start))

        self.issues = [
            Issue(
                idx=i, kind=f.kind, label=f.label, why=f.why,
                original=(f.original[:90] + "…") if len(f.original) > 90 else f.original,
                fix=f.fix, severity=f.severity, auto=f.auto, has_fix=f.has_fix,
                action=("Delete" if f.has_fix and f.fix == ""
                        else "Fix" if f.has_fix else ""),
            )
            for i, f in picked[:MAX_SHOWN]
        ]

    def _build_chunks(self) -> None:
        """Split the essay into plain and marked runs for the review pane.
        Only inline findings mark text — a whole-sentence finding would swallow
        the paragraph and make the highlighting useless."""
        text = self.body or ""
        if not text:
            self.chunks = []
            return
        spans = sorted(
            [(f.start, f.end, f.kind, i) for i, f in enumerate(self._findings)
             if f.kind not in prose.STRUCTURAL and f.end > f.start],
            key=lambda s: s[0])

        out: list[Chunk] = []
        pos = 0
        for start, end, kind, idx in spans:
            if start < pos:
                continue
            if start > pos:
                out.append(Chunk(text=text[pos:start], kind="", idx=-1, marked=False))
            out.append(Chunk(text=text[start:end], kind=kind, idx=idx, marked=True))
            pos = end
        if pos < len(text):
            out.append(Chunk(text=text[pos:], kind="", idx=-1, marked=False))
        self.chunks = out[:600]

    def _build_outline(self, text: str) -> None:
        """The shape of the essay at a glance.

        Paragraph length is the thing writers cannot see in their own work. A
        700-word wall or five one-line stubs are both obvious from three feet
        away and invisible while you are inside them.
        """
        paras = prose.paragraphs(text)
        total = sum(len(prose.words(p)) for p in paras) or 1
        out = []
        for i, p in enumerate(paras, 1):
            n = len(prose.words(p))
            first = " ".join(p.split())[:64]
            out.append(Para(
                n=i, opening=(first + "…") if len(first) == 64 else first,
                words=n, percent=int(round(100 * n / total)),
                tone="short" if n < 35 else "long" if n > 200 else "ok",
            ))
        self.paras = out[:20]

    @rx.event
    def analyse_now(self):
        self._analyse()
        self.flash = (
            f"Read {self.stat_words} words · {self.total_issues} things to look at"
            if self.score_ready else
            f"{self.words_needed} more words before a score means anything.")

    @rx.event
    async def set_body(self, value: str):
        """The browser sends what you typed; nothing is sent back.

        Re-reading the whole essay on every keystroke would be wasteful, so the
        analysis refreshes once the draft has moved by a sentence's worth of
        typing — often enough to feel alive, rarely enough to stay cheap.

        And the same beat writes it to the database. Leaving the box used to
        be the only thing that saved: close the lid, lose the tab, let the
        laptop sleep, and an hour of writing was gone — the one kind of bug a
        student never forgives. A row update of a few kilobytes every
        sentence or so costs nothing next to that, so the draft is never more
        than a sentence away from being on disk.
        """
        self.body = value
        self.flash = ""
        self.last_applied = ""
        self.dirty = True
        if abs(len(value) - self.analysed_len) >= 40:
            self._analyse()
            # A failure here is a sign-out mid-draft. Say nothing and leave
            # dirty set: the blur handler and the Save button both try again,
            # and the text is still in the box either way.
            await self._persist()

    # ---------------------------------------------------------------- fixes
    @rx.event
    async def apply_fix(self, idx: int):
        """Apply one suggestion.

        Nothing is trusted: the index is range-checked, and prose.apply_one
        re-reads the characters at the recorded offsets and refuses if they are
        not still exactly what the analysis saw. A stale tap is a no-op, never
        a mangled sentence.
        """
        if not (0 <= idx < len(self._findings)):
            return
        f = self._findings[idx]
        if not f.has_fix:
            return

        new = prose.apply_one(self.body, f)
        if new == self.body:
            self.flash = "That part changed since I last checked. Checking again."
            self._analyse()
            return

        self._undo_body = self.body
        self._undo_label = f"“{f.original.strip()}”"
        self.body = new
        self.doc_version += 1      # we changed the text, so the box must catch up
        self.last_applied = f.kind
        self.open_issue = -1
        self._analyse()
        self.flash = (f"Deleted “{f.original.strip()}”" if f.fix == ""
                      else f"“{f.original.strip()}” → “{f.fix}”")
        if not await self._persist():
            return rx.redirect("/login")

    @rx.event
    async def polish(self):
        """Apply every high-confidence fix in one go.

        Only the ones marked `auto` in the engine — the mechanical corrections
        where there is no judgement call. Anything about voice or structure is
        left for the writer, because those are the decisions that make the
        essay theirs.
        """
        if not self.auto_count:
            return
        before = self.body
        new, n = prose.apply_all(self.body, self._findings)
        if not n or new == before:
            self.flash = "Nothing I can safely fix automatically."
            return
        self._undo_body = before
        self._undo_label = f"{n} automatic " + ("fix" if n == 1 else "fixes")
        self.body = new
        self.doc_version += 1
        self.open_issue = -1
        old_score = self.score
        self._analyse()
        gain = self.score - old_score
        self.last_applied = "polish"
        self.flash = (f"Applied {n} " + ("fix" if n == 1 else "fixes")
                      + (f" · score {old_score} → {self.score}" if gain else ""))
        if not await self._persist():
            return rx.redirect("/login")

    @rx.event
    async def undo(self):
        if not self._undo_body and not self._undo_label:
            return
        self.body = self._undo_body
        self.doc_version += 1
        self._undo_body = ""
        label, self._undo_label = self._undo_label, ""
        self._analyse()
        self.flash = f"Put {label} back."
        if not await self._persist():
            return rx.redirect("/login")

    @rx.event
    def dismiss(self, idx: int):
        """Not a problem — drop it for this session."""
        if 0 <= idx < len(self._findings):
            self._findings.pop(idx)
            self.total_issues = len(self._findings)
            self.auto_count = sum(1 for f in self._findings if f.auto and f.has_fix)
            self.open_issue = -1
            self._build_issues()
            self._build_chunks()

    @rx.event
    def set_focus(self, kind: str):
        self.focus = "" if self.focus == kind else kind
        self.open_issue = -1
        self._build_issues()

    @rx.event
    def toggle_issue(self, idx: int):
        self.open_issue = -1 if self.open_issue == idx else idx

    @rx.event
    def toggle_review(self):
        self.review_mode = not self.review_mode
        self.outline_mode = False
        if self.review_mode:
            self._analyse()

    @rx.event
    def toggle_outline(self):
        self.outline_mode = not self.outline_mode
        self.review_mode = False
        if self.outline_mode:
            self._analyse()

    # -------------------------------------------------------------- prompts
    @rx.event
    def toggle_prompts(self):
        self.show_prompts = not self.show_prompts

    @rx.event
    def open_prompts(self):
        self.show_prompts = True
        self.coach_open = False      # the drawer would sit on top of the modal

    @rx.event
    def close_prompts(self):
        self.show_prompts = False

    @rx.event
    async def pick_prompt(self, key: str):
        p = promptlib.BY_KEY.get(key)
        if not p:
            return
        self.prompt = p["text"]
        self.prompt_note = p["note"]
        self.word_target = p["words"]
        self.show_prompts = False
        self.flash = f"Prompt set · {p['words']}-word limit"
        if not await self._persist():
            return rx.redirect("/login")

    # ------------------------------------------------------------- versions
    def _load_versions(self, session, uid: int) -> None:
        rows = list(session.exec(
            select(EssayVersion)
            .where(EssayVersion.user_id == uid,
                   EssayVersion.essay_id == self.essay_id)
            .order_by(EssayVersion.created_at.desc())).all())
        out = []
        for i, v in enumerate(rows):
            older = rows[i + 1] if i + 1 < len(rows) else None
            if older:
                d = v.words - older.words
                delta = f"{'+' if d >= 0 else ''}{d} words"
            else:
                delta = "first save"
            out.append(VersionRow(
                id=v.id, label=v.label or "Snapshot",
                when=v.created_at.strftime("%b %d, %H:%M"),
                words=v.words, score=v.score, delta=delta))
        self.versions = out

    @rx.event
    async def snapshot(self):
        """Keep this draft so you can come back to it.

        Undo covers the last change. This covers the other kind of regret: the
        one where you rewrote the whole middle section yesterday and now want
        the old version back.
        """
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        if not (self.body or "").strip():
            self.flash = "Nothing to save yet."
            return
        with db.get_session() as s:
            s.add(EssayVersion(
                user_id=uid, essay_id=self.essay_id, body=self.body,
                words=self.stat_words, score=self.score,
                label=f"{self.stat_words} words · scores {self.score}"))
            s.commit()

            # Trim the oldest so the list stays useful rather than endless.
            rows = list(s.exec(
                select(EssayVersion)
                .where(EssayVersion.user_id == uid,
                       EssayVersion.essay_id == self.essay_id)
                .order_by(EssayVersion.created_at.desc())).all())
            for old in rows[MAX_VERSIONS:]:
                s.delete(old)
            s.commit()
            self._load_versions(s, uid)
        self.show_versions = True
        self.flash = "Version saved."

    @rx.event
    async def restore(self, version_id: int):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        with db.get_session() as s:
            v = s.get(EssayVersion, version_id)
            if not v or v.user_id != uid or v.essay_id != self.essay_id:
                return
            # The draft being replaced is itself worth keeping — restoring
            # should never be the thing that loses work.
            s.add(EssayVersion(
                user_id=uid, essay_id=self.essay_id, body=self.body,
                words=self.stat_words, score=self.score,
                label="Before restore"))
            s.commit()
            self.body = v.body or ""
            self._load_versions(s, uid)

        self.doc_version += 1
        self._undo_body = ""
        self._undo_label = ""
        self._analyse()
        self.flash = "Restored. The draft you replaced was saved first."
        if not await self._persist():
            return rx.redirect("/login")

    @rx.event
    def toggle_versions(self):
        self.show_versions = not self.show_versions

    # -------------------------------------------------------------- saving
    @rx.event
    async def react(self, kind: str):
        self.reaction = "" if self.reaction == kind else kind
        if not await self._persist():
            return rx.redirect("/login")

    async def _persist(self) -> bool:
        """Plain helper, not an event. Event handlers cannot call each other in
        Reflex, so the shared work lives here and each handler awaits it."""
        uid = await self._user_id()
        if uid is None:
            return False
        with db.get_session() as s:
            row = s.get(Essay, self.essay_id)
            if row and row.user_id == uid:
                row.body = self.body
                row.prompt = self.prompt[:300]
                row.word_target = self.word_target
                row.step = self.step
                row.done = self.done
                row.reaction = self.reaction
                row.updated_at = utcnow()
                s.add(row); s.commit()
        self.dirty = False
        self.saved_at = utcnow().strftime("%H:%M")
        return True

    @rx.event
    async def save(self):
        self._analyse()
        if not await self._persist():
            return rx.redirect("/login")

        uid = await self._user_id()
        if uid is not None:
            with db.get_session() as s:
                new = achievements.award(s, uid)
            self.just_earned = new[0]["title"] if new else ""
        self.flash = "Saved."

    @rx.event
    async def next_step(self):
        """The wireframe's "I'm done!" button — moves the guide along."""
        if self.step < len(STEPS) - 1:
            self.step += 1
        else:
            self.done = True
        if not await self._persist():
            return rx.redirect("/login")

    @rx.event
    async def back_step(self):
        self.done = False
        if self.step > 0:
            self.step -= 1
        if not await self._persist():
            return rx.redirect("/login")

    @rx.event
    def dismiss_earned(self):
        self.just_earned = ""


# ====================================================================
# recs_state
# ====================================================================

@dataclasses.dataclass
class SchoolPick:
    """One college, and whether this letter is going to it."""

    id: int
    name: str
    picked: bool


@dataclasses.dataclass
class RecRow:
    id: int
    name: str
    subject: str
    status: str
    status_key: str
    asked: str
    days_waiting: int
    needs_nudge: bool
    nudge_text: str
    help_text: str
    note: str
    schools: list[SchoolPick]
    covers: str            # "3 colleges" / "not assigned yet"
    follow_up: str
    follow_up_iso: str
    follow_due: bool


def _ids(raw: str | None) -> set[int]:
    """Read the comma-separated school id list. Junk is ignored rather than
    raising — this string is only ever written by us, but a corrupted row must
    not take the screen down."""
    out = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


STATUS_FLOW = ["not_asked", "asked", "agreed", "submitted"]
REC_STATUS_LABEL = {"not_asked": "Not asked yet", "asked": "Asked",
                    "agreed": "Said yes", "submitted": "Letter sent"}
STATUS_TONE = {"not_asked": "neutral", "asked": "warn",
               "agreed": "accent", "submitted": "success"}


class RecsState(FeatureState, rx.State):
    tab: str = "teacher"          # teacher | guidance
    rows: list[RecRow] = []

    open_id: int = 0              # whose panel is expanded
    draft_for: int = 0            # whose message is being written
    draft_reason: str = ""
    draft_text: str = ""

    # Which colleges still do not have enough letters pointed at them. This is
    # the question the screen exists to answer and the old one could not.
    short_schools: list[str] = []

    # headline numbers
    needed: int = 0               # most letters any one college asks for
    agreed: int = 0
    asked_count: int = 0
    sent: int = 0
    waiting: int = 0              # asked, gone quiet
    first_deadline: str = ""

    just_earned: str = ""

    @rx.var
    def is_teacher_tab(self) -> bool:
        return self.tab == "teacher"

    @rx.var
    def list_label(self) -> str:
        return "List of teachers" if self.tab == "teacher" else "School counselors"

    @rx.var(deps=["agreed", "needed"])
    def cover_line(self) -> str:
        if self.needed == 0:
            return ("Add a college with a deadline to see how many letters you need.")
        if self.agreed >= self.needed:
            return f"You have all {self.needed} letters covered."
        short = self.needed - self.agreed
        return (f"{self.agreed} of {self.needed} covered. You need "
                f"{short} more {'teacher' if short == 1 else 'teachers'} to say yes.")

    @rx.var(deps=["agreed", "needed"])
    def cover_percent(self) -> int:
        if not self.needed:
            return 0
        return min(100, int(round(100 * self.agreed / self.needed)))

    @rx.var(deps=["tab"])
    def guide_title(self) -> str:
        return asking.TEMPLATES[self.tab]["title"]

    @rx.var(deps=["tab"])
    def guide_when(self) -> str:
        return asking.TEMPLATES[self.tab]["when"]

    @rx.var(deps=["tab"])
    def guide_how(self) -> str:
        return asking.TEMPLATES[self.tab]["how"]

    @rx.var(deps=["tab"])
    def reason_hint(self) -> str:
        return asking.TEMPLATES[self.tab]["reason_hint"]
    # ---------------------------------------------------------------- load
    @rx.event
    async def load(self):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        self._refresh(uid)
        self.loading = False

    @rx.event
    async def set_tab(self, tab: str):
        self.tab = tab if tab in ("teacher", "guidance") else "teacher"
        self.open_id = 0
        self.draft_for = 0
        uid = await self._user_id()
        if uid is not None:
            self._refresh(uid)

    def _refresh(self, uid: int) -> None:
        today = utcnow().date()
        with db.get_session() as s:
            rows = list(s.exec(select(Recommender)
                               .where(Recommender.user_id == uid,
                                      Recommender.role == self.tab)).all())
            # name is encrypted, so sorting happens in Python after decryption
            rows.sort(key=lambda r: (r.name or "").lower())

            all_schools = list(s.exec(select(School)
                                      .where(School.user_id == uid)
                                      .order_by(School.name)).all())

            packed = []
            for r in rows:
                days = (today - r.asked_on.date()).days if r.asked_on else 0
                quiet = (r.status == "asked" and days >= asking.NUDGE_DAYS)
                mine = _ids(r.school_ids)
                picks = [SchoolPick(id=sc.id, name=sc.name, picked=sc.id in mine)
                         for sc in all_schools]
                n = sum(1 for p in picks if p.picked)
                due = bool(r.follow_up_on and r.follow_up_on.date() <= today
                           and r.status in ("asked", "agreed"))
                packed.append(RecRow(
                    id=r.id, name=r.name or "(no name)", subject=r.subject or "",
                    status=REC_STATUS_LABEL.get(r.status, r.status),
                    status_key=r.status,
                    asked=r.asked_on.strftime("%b %d") if r.asked_on else "",
                    days_waiting=days, needs_nudge=quiet,
                    nudge_text=asking.NUDGE.format(days=days) if quiet else "",
                    help_text=asking.STATUS_HELP.get(r.status, ""),
                    note=r.note or "",
                    schools=picks,
                    covers=(f"{n} " + ("college" if n == 1 else "colleges")
                            if n else "not pointed at a college yet"),
                    follow_up=(r.follow_up_on.strftime("%b %d")
                               if r.follow_up_on else ""),
                    follow_up_iso=(r.follow_up_on.strftime("%Y-%m-%d")
                                   if r.follow_up_on else ""),
                    follow_due=due,
                ))
            self.rows = packed

            # Every recommender counts toward cover, not just this tab's.
            everyone = list(s.exec(select(Recommender)
                                   .where(Recommender.user_id == uid)).all())
            schools = list(s.exec(select(School)
                                  .where(School.user_id == uid)).all())
            self.needed = max((sc.recs_required or 0 for sc in schools), default=0)
            self.agreed = sum(1 for r in everyone
                              if r.status in ("agreed", "submitted"))
            self.asked_count = sum(1 for r in everyone
                                   if r.status in ("asked", "agreed", "submitted"))
            self.sent = sum(1 for r in everyone if r.status == "submitted")
            self.waiting = sum(1 for r in packed if r.needs_nudge)

            # Which colleges are still short of letters. Counts only the
            # people who have actually agreed — being asked is not a letter.
            secured = [r for r in everyone if r.status in ("agreed", "submitted")]
            short = []
            for sc in schools:
                need = sc.recs_required or 0
                if not need:
                    continue
                got = sum(1 for r in secured if sc.id in _ids(r.school_ids))
                # A letter with no colleges assigned is assumed to go
                # everywhere, which is what actually happens with a general
                # teacher recommendation.
                got += sum(1 for r in secured if not _ids(r.school_ids))
                if got < need:
                    short.append(f"{sc.name} ({got}/{need})")
            self.short_schools = short

            dated = sorted([sc for sc in schools if sc.deadline],
                           key=lambda sc: sc.deadline)
            self.first_deadline = (dated[0].deadline.strftime("%B %d")
                                   if dated else "")

            stats = achievements.gather(s, uid)
            new = achievements.award(s, uid, stats)
            self.just_earned = new[0]["title"] if new else ""

    # -------------------------------------------------------------- editing
    @rx.event
    async def add(self, form: dict):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        name = (form.get("name") or "").strip()
        if not name:
            self.error = "Add their name first."
            return
        with db.get_session() as s:
            s.add(Recommender(user_id=uid, name=name[:80],
                              subject=(form.get("subject") or "").strip()[:60],
                              role=self.tab))
            s.commit()
        self.error = ""
        self._refresh(uid)

    @rx.event
    def toggle_open(self, rec_id: int):
        self.open_id = 0 if self.open_id == rec_id else rec_id
        self.draft_for = 0

    @rx.event
    async def set_status(self, rec_id: int, status: str):
        """Set the stage directly. The old screen could only move forward one
        step, which made a mistyped click impossible to undo."""
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        if status not in STATUS_FLOW:
            return
        with db.get_session() as s:
            row = s.get(Recommender, rec_id)
            if row and row.user_id == uid:
                row.status = status
                if status in ("asked", "agreed", "submitted") and row.asked_on is None:
                    row.asked_on = utcnow()
                if status == "not_asked":
                    row.asked_on = None
                s.add(row); s.commit()
        self._refresh(uid)

    @rx.event
    async def advance(self, rec_id: int):
        """Nudge one person along: not asked -> asked -> said yes -> letter sent."""
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        with db.get_session() as s:
            row = s.get(Recommender, rec_id)
            if row and row.user_id == uid:
                i = STATUS_FLOW.index(row.status) if row.status in STATUS_FLOW else 0
                row.status = STATUS_FLOW[min(i + 1, len(STATUS_FLOW) - 1)]
                if row.status == "asked" and row.asked_on is None:
                    row.asked_on = utcnow()
                s.add(row); s.commit()
        self._refresh(uid)

    @rx.event
    async def set_note(self, rec_id: int, value: str):
        """What they taught you, what you want mentioned — the things you will
        have forgotten by the time they ask."""
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        with db.get_session() as s:
            row = s.get(Recommender, rec_id)
            if row and row.user_id == uid:
                row.note = value[:2000]
                s.add(row); s.commit()
        self._refresh(uid)

    @rx.event
    async def remove(self, rec_id: int):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        with db.get_session() as s:
            row = s.get(Recommender, rec_id)
            if row and row.user_id == uid:
                s.delete(row); s.commit()
        if self.open_id == rec_id:
            self.open_id = 0
        self._refresh(uid)

    # ------------------------------------------------------- the ask itself
    @rx.event
    async def start_draft(self, rec_id: int):
        """Write the message for them. This is the point of the screen."""
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        self.draft_for = rec_id
        row = next((r for r in self.rows if r.id == rec_id), None)
        with db.get_session() as s:
            user = s.get(User, uid)
        self.draft_reason = row.note if row else ""
        self.draft_text = asking.message(
            self.tab,
            teacher=row.name if row and row.name != "(no name)" else "",
            name=user.username if user else "",
            deadline=self.first_deadline,
            reason=self.draft_reason,
        )

    @rx.event
    def set_draft_reason(self, value: str):
        self.draft_reason = value

    @rx.event
    async def rebuild_draft(self):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        row = next((r for r in self.rows if r.id == self.draft_for), None)
        with db.get_session() as s:
            user = s.get(User, uid)
        self.draft_text = asking.message(
            self.tab,
            teacher=row.name if row and row.name != "(no name)" else "",
            name=user.username if user else "",
            deadline=self.first_deadline,
            reason=self.draft_reason,
        )

    @rx.event
    def close_draft(self):
        self.draft_for = 0
        self.draft_text = ""
        self.draft_reason = ""

    @rx.event
    async def toggle_school(self, rec_id: int, school_id: int):
        """Point this letter at a college, or stop pointing it there."""
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        with db.get_session() as s:
            row = s.get(Recommender, rec_id)
            school = s.get(School, school_id)
            if (row and row.user_id == uid and school and school.user_id == uid):
                ids = _ids(row.school_ids)
                ids.discard(school_id) if school_id in ids else ids.add(school_id)
                row.school_ids = ",".join(str(i) for i in sorted(ids))[:200]
                s.add(row); s.commit()
        self._refresh(uid)

    @rx.event
    async def set_follow_up(self, rec_id: int, value: str):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        when = None
        if value:
            try:
                when = datetime.strptime(value, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc)
            except ValueError:
                self.error = "That date didn't make sense."
                return
        with db.get_session() as s:
            row = s.get(Recommender, rec_id)
            if row and row.user_id == uid:
                row.follow_up_on = when
                s.add(row); s.commit()
        self.error = ""
        self._refresh(uid)

    @rx.event
    async def remind_in_two_weeks(self, rec_id: int):
        """The common case, as one button. Nothing is emailed — it only
        surfaces on this screen, which is where you will be anyway."""
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        with db.get_session() as s:
            row = s.get(Recommender, rec_id)
            if row and row.user_id == uid:
                row.follow_up_on = utcnow() + timedelta(days=14)
                s.add(row); s.commit()
        self._refresh(uid)

    @rx.event
    def dismiss_earned(self):
        self.just_earned = ""
