"""
Profile state: career interest, major, extracurriculars, timeline.

This is the personalisation foundation. What a student says here feeds the
readiness engine (services/readiness.py) and, later, the college and essay
screens — so it is stored on the user row rather than held in the session.

Everything lives in one JSON column (`User.profile_data`) on purpose. These
fields are read and written together, always for one user, and never queried
or sorted across users. A table per shape would be five migrations for no
gain; the day one of these needs an index, it earns its own column then.
"""

from __future__ import annotations

import json

import reflex as rx
from sqlmodel import select

from veritagnosis import db
from veritagnosis.models import School, TestScore, User
from veritagnosis.crypto import DecryptionError
from veritagnosis.services import activities as activity_svc, catalog
from veritagnosis.services import insight as fit_svc
from veritagnosis.services import insight as readiness_svc
from veritagnosis.states.base import FeatureState

# Fixed scales, so a band drawn for one college is directly comparable to the
# band drawn for the next. Scaling each bar to its own college would make a
# narrow band look as wide as a broad one.
SCALES = {"SAT": (400, 1600), "ACT": (1, 36)}

# Plain module constants, not state vars. Reflex ships every state var to the
# browser on each update; this list never changes, so it belongs in the
# compiled page, not in the state payload.
CAREER_OPTIONS = [
    "Computer Science", "Medicine", "Business", "Engineering", "Law",
    "Education", "Psychology", "Biology", "Chemistry", "Physics",
    "Economics", "Liberal Arts", "Architecture", "Nursing", "Art/Design",
    "Music", "Undecided",
]

MAJOR_OPTIONS = [
    "Computer Science", "Computer Engineering", "Electrical Engineering",
    "Mechanical Engineering", "Biomedical Engineering", "Biology",
    "Chemistry", "Physics", "Psychology", "Economics",
    "Business Administration", "Finance", "Accounting", "Marketing",
    "English Literature", "History", "Philosophy", "Pre-Med", "Pre-Law",
    "Nursing", "Environmental Science",
]

INTENSITIES = ["light", "moderate", "intense"]

# Event handlers are reachable over the websocket directly, so what the UI
# offers is not a constraint on what arrives. Anything free-text is capped
# here; anything that should be one of a fixed set is checked against it.
MAX_FIELD = 80
MAX_ACTIVITIES = 30


class ProfileState(FeatureState, rx.State):
    """Student profile: background, interests, goals, timeline."""

    # Your own numbers.
    #
    # The scoring engine has read these since it was written — student_stats()
    # parses user.gpa and the TestScore rows, the fit bands compare them
    # against each college's published percentiles, and the readiness score
    # weights them. There was simply nowhere in the app to type them, so every
    # student got the same answer: "you have not entered an SAT or ACT score".
    #
    # Held as strings because that is what a text input gives, and because a
    # half-typed "14" must not be stored as a real score. Parsing and range
    # checks happen on save.
    gpa_input: str = ""
    sat_input: str = ""
    act_input: str = ""
    scores_msg: str = ""

    career_interest: str = ""
    major_preference: str = ""

    # One row per activity: {name, intensity, years, leadership}.
    # Held as a typed list so rx.foreach can walk it in the page; it is
    # serialised into the JSON column on save.
    extracurriculars: list[dict[str, str]] = []

    @rx.var(deps=["extracurriculars"])
    def ec_rows(self) -> list[dict[str, str]]:
        """The activities as the page shows them, each with what it scored
        and why ("intense +15 · 3 years +6 · “captain” +10"), so a student can
        see exactly which words and choices moved their readiness."""
        out = []
        for r in self.extracurriculars:
            sc = activity_svc.score_one(r)
            out.append({**r, "points": str(sc.points),
                        "signals": " · ".join(sc.signals)})
        return out

    app_deadline: str = ""          # "2026-01-15"
    target_schools_count: int = 5
    priority: str = "balanced"      # reach | balanced | safety

    # Draft fields for the "add an activity" row.
    new_ec_name: str = ""
    new_ec_intensity: str = "moderate"
    new_ec_years: str = "1"

    saved_msg: str = ""
    load_error: str = ""

    # Bumped only when a field is deliberately cleared or reloaded. It feeds
    # the inputs' React `key`, and that is the whole point: a key built from
    # the field's own value changes on every keystroke, which remounts the
    # input and throws away the caret after a single character. Typing into
    # the box then appears to do nothing. Tying the key to an explicit counter
    # means the input is only ever rebuilt when we actually mean to reset it.
    form_epoch: int = 0

    # ---- computed on load, read-only on the page -------------------------
    # Held as plain strings because Reflex ships state to the browser and a
    # typed list var will not take mixed types. The engines return rich
    # objects; they are flattened here rather than in the template.
    readiness_overall: int = 0
    readiness_dims: list[dict[str, str]] = []
    blind_spots: list[dict[str, str]] = []
    next_steps: list[str] = []

    fits: list[dict[str, str]] = []
    disagreements: list[dict[str, str]] = []
    fit_warnings: list[str] = []
    school_count: int = 0
    analysed: bool = False

    @rx.var
    def profile_complete(self) -> bool:
        """Enough to personalise anything at all."""
        return bool(self.career_interest or self.major_preference)

    # -- simple setters ----------------------------------------------------
    # Each clears saved_msg so the "Saved ✓" tick never lingers over an edit
    # that has not been written yet.

    @rx.event
    def set_career_interest(self, value: str):
        self.career_interest = str(value)[:MAX_FIELD]
        self.saved_msg = ""

    @rx.event
    def set_major_preference(self, value: str):
        self.major_preference = str(value)[:MAX_FIELD]
        self.saved_msg = ""

    @rx.event
    def set_app_deadline(self, value: str):
        # An <input type=date> sends YYYY-MM-DD; anything else is discarded
        # rather than stored, since this is later parsed as a date.
        v = str(value)[:10]
        if v and not (len(v) == 10 and v[4] == "-" and v[7] == "-"
                      and v.replace("-", "").isdigit()):
            return
        self.app_deadline = v
        self.saved_msg = ""

    @rx.event
    def set_target_schools_count(self, value: float):
        """Annotated float because that is what Reflex sends from an
        <input type=number>. It can still arrive empty mid-typing, which is
        not an error worth showing anyone — the old value just stands."""
        try:
            n = int(value)
        except (TypeError, ValueError):
            return
        self.target_schools_count = max(1, min(20, n))
        self.saved_msg = ""

    @rx.event
    def set_priority(self, value: str):
        if value in ("reach", "balanced", "safety"):
            self.priority = value
            self.saved_msg = ""

    # -- extracurriculars --------------------------------------------------

    @rx.event
    def set_new_ec_name(self, value: str):
        self.new_ec_name = str(value)[:MAX_FIELD]

    @rx.event
    def set_new_ec_intensity(self, value: str):
        if value in INTENSITIES:
            self.new_ec_intensity = value

    @rx.event
    def set_new_ec_years(self, value: float):
        try:
            self.new_ec_years = str(int(value))
        except (TypeError, ValueError):
            return

    @rx.event
    def add_extracurricular(self):
        """Add the drafted activity and clear the draft row."""
        name = self.new_ec_name.strip()
        if not name or len(self.extracurriculars) >= MAX_ACTIVITIES:
            return
        try:
            years = max(1, min(6, int(self.new_ec_years)))
        except (TypeError, ValueError):
            years = 1

        # Rebound rather than .append(): Reflex tracks assignment to a var, so
        # mutating the list in place would not re-render the page.
        self.extracurriculars = self.extracurriculars + [{
            "name": name[:60],
            "intensity": self.new_ec_intensity,
            "years": str(years),
            "leadership": "no",
        }]
        self.new_ec_name = ""
        self.new_ec_years = "1"
        self.form_epoch += 1      # clear the inputs, deliberately
        self.saved_msg = ""
        return ProfileState.store_activities

    @rx.event
    def remove_extracurricular(self, index: int):
        if 0 <= index < len(self.extracurriculars):
            rows = list(self.extracurriculars)
            rows.pop(index)
            self.extracurriculars = rows
            self.saved_msg = ""
            return ProfileState.store_activities

    @rx.event
    def toggle_leadership(self, index: int):
        if 0 <= index < len(self.extracurriculars):
            rows = [dict(r) for r in self.extracurriculars]
            rows[index]["leadership"] = (
                "no" if rows[index].get("leadership") == "yes" else "yes"
            )
            self.extracurriculars = rows
            self.saved_msg = ""
            return ProfileState.store_activities

    # -- persistence -------------------------------------------------------

    @rx.event
    async def store_activities(self):
        """Activities save the moment they change, and the readiness numbers
        above move with them. Waiting for "Save profile" meant adding a
        captaincy did nothing visible, which reads as the feature not working.
        """
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        self._write_profile(uid)
        self._analyse(uid)

    @rx.event
    async def load(self):
        """Read the profile off the user row on page load."""
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")

        # The decrypt happens here, inside the ORM read, so it has to be
        # guarded: an unreadable profile_data must not take the whole screen
        # down with it. Unlike an essay, everything in this blob is a handful
        # of choices the student can simply pick again, so an empty form with
        # an explanation beats a page that will not open.
        raw = None
        try:
            with db.get_session() as s:
                user = s.get(User, uid)
                raw = user.profile_data if user else None
        except DecryptionError:
            self.load_error = (
                ("We couldn't load your saved profile, so the form is blank. Filling "
                 'it in again will fix it. Nothing else on your account was affected.')
            )
            raw = None

        # The GPA and the scores live in their own columns and rows, not in
        # profile_data, so they are read separately and survive an unreadable
        # blob. Guarded for the same reason the read above is: this screen must
        # open even when one stored value cannot be read, because everything on
        # it can simply be entered again.
        try:
            with db.get_session() as s:
                self._load_scores(s, uid)
        except Exception:                                      # noqa: BLE001
            self.gpa_input = self.sat_input = self.act_input = ""

        if raw:
            try:
                p = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                p = {}
            self.career_interest = p.get("career_interest", "")
            self.major_preference = p.get("major_preference", "")
            self.app_deadline = p.get("app_deadline", "")
            self.target_schools_count = p.get("target_schools_count", 5)
            self.priority = p.get("priority", "balanced")

            # Coerce every field to str: these came out of JSON that an older
            # version of this screen may have written with ints and bools, and
            # a typed list var will not accept mixed types.
            rows = []
            for ec in p.get("extracurriculars", []) or []:
                if not isinstance(ec, dict):
                    continue
                lead = ec.get("leadership")
                rows.append({
                    "name": str(ec.get("name", "")),
                    "intensity": str(ec.get("intensity", "moderate")),
                    "years": str(ec.get("years", "1")),
                    "leadership": "yes" if lead in (True, "yes") else "no",
                })
            self.extracurriculars = rows

        self.form_epoch += 1      # the loaded values are new; refresh the inputs
        self._analyse(uid)
        self.loading = False

    def _analyse(self, uid: int) -> None:
        """Run both engines and flatten them for the page.

        Wrapped because a student with a half-filled profile is the normal
        case, not an error: if either engine raises, the screen still renders
        with whatever the other produced rather than showing a stack trace to
        a seventeen-year-old."""
        try:
            r = readiness_svc.assess(uid)
            self.readiness_overall = int(round(r.overall))
            self.readiness_dims = [
                # int(): one of the scores is worked out as a float, and
                # "0.0" next to four whole numbers looks like a glitch.
                {"key": k, "label": lbl, "score": str(int(round(v))),
                 "pct": f"{int(round(v))}%",
                 "why": r.explanations.get(k, "")}
                for k, lbl, v in (
                    ("academic", "Academic", r.academic),
                    ("extracurricular", "Activities", r.extracurricular),
                    ("college_fit", "College list", r.college_fit),
                    ("application_progress", "Applications", r.application_progress),
                    ("financial_readiness", "Paying for it", r.financial_readiness),
                )
            ]
            self.blind_spots = [
                {"icon": str(b.get("icon", "•")),
                 "title": str(b.get("title", "")),
                 "body": str(b.get("explanation", b.get("body", ""))),
                 "action": str(b.get("action", ""))}
                for b in r.blind_spots
            ]
            self.next_steps = [str(x) for x in r.next_steps]
        except Exception:
            self.readiness_overall = 0
            self.readiness_dims = []
            self.blind_spots = []
            self.next_steps = []

        try:
            rv = fit_svc.review(uid)
            self.fits = [self._flatten_fit(f) for f in rv["fits"]]
            self.disagreements = [self._flatten_fit(f) for f in rv["disagreements"]]
            self.fit_warnings = [str(w) for w in rv["warnings"]]
            self.school_count = len(rv["fits"])
            self.analysed = True
        except Exception:
            self.fits = []
            self.disagreements = []
            self.fit_warnings = []
            self.analysed = False

    @staticmethod
    def _flatten_fit(f) -> dict[str, str]:
        """One college, reduced to strings and CSS percentages.

        The bar geometry is worked out here rather than in the browser so the
        template stays declarative and the numbers can be tested."""
        st = f.standings[0] if f.standings else None
        row = {
            "name": f.school_name,
            "student_tier": f.student_tier,
            "data_tier": f.data_tier or "",
            "has_data": "yes" if f.has_data else "no",
            "accept_rate": f"{f.accept_rate}%" if f.accept_rate is not None else "",
            "cost": f"${f.cost_year:,}" if f.cost_year else "",
            "data_year": f.data_year,
            "source_url": f.source_url,
            "confidence": f.confidence,
            "caveat": " ".join(f.caveats),
            "disagrees": "yes" if f.disagrees else "no",
            "school_id": str(getattr(f, "school_id", 0) or 0),
            "sug1": "", "sug2": "", "sug3": "",
            "metric": "", "sentence": "", "place": "",
            "band_left": "0%", "band_width": "0%", "marker": "0%",
            "low": "", "high": "", "value": "",
        }
        if st is not None:
            lo_s, hi_s = SCALES.get(st.metric, (st.low, st.high))
            span = float(hi_s - lo_s) or 1.0
            clamp = lambda x: max(0.0, min(100.0, x))
            row.update({
                "metric": st.metric,
                "sentence": st.sentence,
                "place": st.place,
                "band_left": f"{clamp((st.low - lo_s) / span * 100):.1f}%",
                "band_width": f"{clamp((st.high - st.low) / span * 100):.1f}%",
                "marker": f"{clamp((st.value - lo_s) / span * 100):.1f}%",
                "low": str(int(st.low)), "high": str(int(st.high)),
                "value": str(int(st.value)),
            })
        for i, name in enumerate((getattr(f, "suggestions", None) or [])[:3], 1):
            row[f"sug{i}"] = str(name)
        return row

    @rx.event
    async def rename_school(self, school_id: str, name: str):
        """Replace a name the catalogue did not recognise with a full one.

        Only the student's own row, and only a name the catalogue resolves,
        so this cannot be used to write an arbitrary string."""
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        try:
            sid = int(school_id)
        except (TypeError, ValueError):
            return
        with db.get_session() as s:
            row = s.get(School, sid)
            match = catalog.resolve(s, name)
            if row is None or row.user_id != uid or match is None:
                return
            row.name = match.name[:120]
            s.add(row)
            s.commit()
        self._analyse(uid)

    def _load_scores(self, session, uid: int) -> None:
        """Fill the inputs from what is stored.

        Without this the form is blank on every visit and a student retypes
        their GPA each time — which also makes it impossible to tell "I have
        not entered this" from "the form forgot".
        """
        user = session.get(User, uid)
        try:
            self.gpa_input = str(user.gpa or "") if user else ""
        except DecryptionError:
            # Same tolerance the rest of this screen has for an unreadable
            # column: show it empty rather than failing the whole page.
            self.gpa_input = ""
        self.sat_input = ""
        self.act_input = ""
        for r in session.exec(
                select(TestScore).where(TestScore.user_id == uid)).all():
            kind = (r.kind or "").strip().upper()
            if kind == "SAT":
                self.sat_input = str(r.score or "")
            elif kind == "ACT":
                self.act_input = str(r.score or "")

    @rx.event
    async def refresh_analysis(self):
        """Recompute without a full page load, after the student edits."""
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        self._analyse(uid)

    @rx.event
    def set_gpa_input(self, value: str):
        # Digits and one dot only: a GPA is a number, and letting anything
        # else through means storing something student_stats will silently drop.
        cleaned = "".join(c for c in value if c.isdigit() or c == ".")
        if cleaned.count(".") > 1:
            head, _, tail = cleaned.partition(".")
            cleaned = head + "." + tail.replace(".", "")
        self.gpa_input = cleaned[:5]
        self.scores_msg = ""

    @rx.event
    def set_sat_input(self, value: str):
        self.sat_input = "".join(c for c in value if c.isdigit())[:4]
        self.scores_msg = ""

    @rx.event
    def set_act_input(self, value: str):
        self.act_input = "".join(c for c in value if c.isdigit())[:2]
        self.scores_msg = ""

    @rx.var(deps=["gpa_input"])
    def gpa_problem(self) -> str:
        """Said while they type, not after they save."""
        if not self.gpa_input:
            return ""
        try:
            g = float(self.gpa_input)
        except ValueError:
            return "That's not a number."
        return "" if 0.0 <= g <= 5.0 else "A GPA is between 0 and 5."

    @rx.var(deps=["sat_input"])
    def sat_problem(self) -> str:
        if not self.sat_input:
            return ""
        v = int(self.sat_input)
        return "" if 400 <= v <= 1600 else "The SAT runs 400 to 1600."

    @rx.var(deps=["act_input"])
    def act_problem(self) -> str:
        if not self.act_input:
            return ""
        v = int(self.act_input)
        return "" if 1 <= v <= 36 else "The ACT runs 1 to 36."

    @rx.var(deps=["gpa_problem", "sat_problem", "act_problem"])
    def scores_ok(self) -> bool:
        return not (self.gpa_problem or self.sat_problem or self.act_problem)

    @rx.event
    async def save_scores(self):
        """Store the GPA and scores, then re-run the analysis immediately.

        Out-of-range values are refused rather than stored, because the engine
        drops what it cannot parse — so a typo would otherwise look saved and
        change nothing, which is the worst of both.
        """
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        if not self.scores_ok:
            self.scores_msg = "Fix the highlighted number first."
            return

        with db.get_session() as s:
            user = s.get(User, uid)
            if user is None:
                return rx.redirect("/login")
            # Blank means "remove it", not "leave the old one".
            user.gpa = self.gpa_input.strip() or None
            s.add(user)

            for kind, raw in (("SAT", self.sat_input), ("ACT", self.act_input)):
                rows = list(s.exec(
                    select(TestScore).where(TestScore.user_id == uid,
                                            TestScore.kind == kind)).all())
                if raw.strip():
                    if rows:
                        rows[0].score = raw.strip()
                        s.add(rows[0])
                        extra = rows[1:]
                    else:
                        s.add(TestScore(user_id=uid, kind=kind,
                                        score=raw.strip()))
                        extra = []
                else:
                    extra = rows
                # One row per kind. student_stats keeps the best of each, so
                # duplicates were harmless but made "clear my score" impossible.
                for r in extra:
                    s.delete(r)
            s.commit()

        self.scores_msg = 'Saved. Everything above now uses these numbers.'
        self._analyse(uid)

    @rx.event
    async def save_profile(self):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")

        self._write_profile(uid)
        self.saved_msg = "Saved ✓"
        # The readiness numbers read the profile, so they change with it.
        self._analyse(uid)

    def _write_profile(self, uid: int) -> None:
        blob = json.dumps({
            "career_interest": self.career_interest,
            "major_preference": self.major_preference,
            "extracurriculars": [
                {k: str(r.get(k, "")) for k in ("name", "intensity", "years", "leadership")}
                for r in self.extracurriculars],
            "app_deadline": self.app_deadline,
            "target_schools_count": self.target_schools_count,
            "priority": self.priority,
        })
        with db.get_session() as s:
            user = s.get(User, uid)
            if user:
                user.profile_data = blob
                s.add(user)
                s.commit()
