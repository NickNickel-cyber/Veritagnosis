"""Paying for college — the paperwork, the costs, and the scholarships."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import reflex as rx
from sqlmodel import select

from veritagnosis import db
from veritagnosis.content import aid as content
from veritagnosis.models import School, Scholarship, utcnow
from veritagnosis.services import wellbeing as achievements, money as aid, money as fafsa
from veritagnosis.states.base import FeatureState


@dataclasses.dataclass
class StepRow:
    key: str
    phase: str
    title: str
    detail: str
    xp: int
    done: bool


@dataclasses.dataclass
class CostRow:
    id: int
    name: str
    sticker: str
    aid: str
    net: str
    known: bool
    round_name: str
    binding: bool
    needs_css: bool
    aid_deadline: str
    bar: int            # share of the dearest, for the comparison bars


@dataclasses.dataclass
class SchRow:
    id: int
    name: str
    amount: str
    deadline: str
    deadline_iso: str
    status: str
    status_key: str
    url: str
    days: int
    urgent: bool


@dataclasses.dataclass
class FlagRow:
    level: str
    title: str
    detail: str


@dataclasses.dataclass
class Term:
    word: str
    meaning: str


@dataclasses.dataclass
class PayRow:
    """One college archetype, priced against this student's own numbers."""

    key: str
    name: str
    blurb: str
    cost: str
    need: str
    met: str
    pell: str
    you_pay: str
    meets: int
    bar: int            # share of the dearest, for the comparison bars
    best: bool


@dataclasses.dataclass
class MyCollegeRow:
    """One college from the student's real list, priced against their SAI.

    Two figures rather than one, on purpose: we have each college's published
    sticker price but not its percent-of-need-met, and inventing that would
    put a confident, possibly very wrong number in front of a family deciding
    whether they can afford college."""

    name: str
    cost: str
    need: str
    pell: str
    generous: str
    typical: str
    data_year: str
    source_url: str
    has_cost: bool
    best: bool


@dataclasses.dataclass
class PartRow:
    """One line of the SAI, so the total is never a black box."""

    label: str
    amount: str
    note: str
    weight: int         # share of the total, for the bar


@dataclasses.dataclass
class ExpRow:
    key: str
    label: str
    teaches: str
    delta: str          # what it does to the SAI, already worded
    direction: str      # up | down | flat


class AidState(FeatureState, rx.State):
    # checklist | simulator | costs | scholarships | learn
    tab: str = "checklist"

    steps: list[StepRow] = []
    phases: list[str] = []
    checklist_percent: int = 0
    done_count: int = 0
    step_total: int = 0

    cost_rows: list[CostRow] = []
    flag_rows: list[FlagRow] = []
    scholarships: list[SchRow] = []
    glossary: list[Term] = []

    # headline numbers
    priced: int = 0
    total_schools: int = 0
    cheapest: str = ""
    cheapest_net: str = "—"
    spread: str = "—"
    won: str = "—"
    chasing: str = "—"

    open_school: int = 0
    just_earned: str = ""

    # ---- the simulator's inputs. Plain ints so the sliders bind directly.
    sim_income: int = 65_000
    sim_household: int = 4
    sim_in_college: int = 1
    sim_single: bool = False
    sim_parent_savings: int = 15_000
    sim_student_income: int = 3_000
    sim_student_savings: int = 1_200
    sim_touched: bool = False       # has the student moved anything yet

    DISCLAIMER: str = content.DISCLAIMER

    # ------------------------------------------------------------ simulator
    def _household(self) -> fafsa.Household:
        return fafsa.Household(
            income=self.sim_income,
            household=self.sim_household,
            in_college=self.sim_in_college,
            single_parent=self.sim_single,
            parent_savings=self.sim_parent_savings,
            student_income=self.sim_student_income,
            student_savings=self.sim_student_savings,
        )

    # Formatted on the server. Var arithmetic in the browser has no thousands
    # separator, and "$65000" beside a slider is exactly the kind of number
    # nobody can read at a glance.
    @rx.var(cache=True)
    def sim_income_label(self) -> str:
        return f"${self.sim_income:,}"

    @rx.var(cache=True)
    def sim_parent_savings_label(self) -> str:
        return f"${self.sim_parent_savings:,}"

    @rx.var(cache=True)
    def sim_student_income_label(self) -> str:
        return f"${self.sim_student_income:,}"

    @rx.var(cache=True)
    def sim_student_savings_label(self) -> str:
        return f"${self.sim_student_savings:,}"

    @rx.var(cache=True)
    def sim(self) -> dict:
        """Everything the simulator screen needs, computed in one place."""
        r = fafsa.student_aid_index(self._household())
        return {
            "sai": f"{r.sai:,}",
            "pell": f"{r.pell:,}",
            "basis": r.pell_basis,
            "pct": r.pct_of_poverty,
            "line": f"{r.poverty_line:,}",
            "negative": r.sai < 0,
        }

    @rx.var(cache=True)
    def sim_parts(self) -> list[PartRow]:
        r = fafsa.student_aid_index(self._household())
        raw = [
            ("Parents' income", r.parent_income_part,
             "This one matters most."),
            ("Parents' savings", r.parent_asset_part,
             f"Only the part above ${fafsa.ASSET_PROTECTION:,} counts, and "
             "only 12% of that is added in, so each dollar saved adds just a "
             "few cents here. Your home and retirement accounts don't count "
             "at all."),
            ("Your own earnings", r.student_income_part,
             f"Protected up to ${fafsa.STUDENT_INCOME_PROTECTION:,}. "
             "Above that, half of it counts."),
            ("Your own savings", r.student_asset_part,
             ("20% of it counts, the highest rate in the formula. Money in a "
              "parent's name counts for less than money in yours.")),
        ]
        total = sum(max(0, v) for _, v, _ in raw) or 1
        return [PartRow(label=l, amount=f"${v:,}", note=n,
                        weight=int(round(100 * max(0, v) / total)))
                for l, v, n in raw]

    @rx.var(cache=True)
    def sim_pay(self) -> list[PayRow]:
        r = fafsa.student_aid_index(self._household())
        rows = fafsa.what_you_would_pay(r)
        dearest = max((e.you_pay for e in rows), default=0) or 1
        return [
            PayRow(key=e.key, name=e.name, blurb=e.blurb,
                   cost=f"${e.cost:,}", need=f"${e.need:,}", met=f"${e.met:,}",
                   pell=f"${e.pell:,}", you_pay=f"${e.you_pay:,}",
                   meets=e.meets, bar=int(round(100 * e.you_pay / dearest)),
                   best=(i == 0))
            for i, e in enumerate(rows)
        ]

    @rx.var(cache=True)
    def my_colleges(self) -> list[MyCollegeRow]:
        """The simulator, pointed at the student's actual list.

        The four archetypes above teach the shape. This answers the question
        they actually walked in with."""
        r = fafsa.student_aid_index(self._household())
        with db.get_session() as s:
            schools = list(s.exec(
                select(School).where(School.user_id == self.owner_id)).all())
            # Inside the session: pricing now consults the imported College
            # Scorecard catalogue for any school not in the curated file.
            rows = fafsa.price_your_list(r, schools, s)
        priced = [e for e in rows if e.has_cost]
        cheapest = priced[0].name if priced else ""
        return [
            MyCollegeRow(
                name=e.name,
                cost=f"${e.cost:,}" if e.has_cost else "",
                need=f"${e.need:,}" if e.has_cost else "",
                pell=f"${e.pell:,}" if e.has_cost else "",
                generous=f"${e.pay_if_generous:,}" if e.has_cost else "",
                typical=f"${e.pay_if_typical:,}" if e.has_cost else "",
                data_year=e.data_year, source_url=e.source_url,
                has_cost=e.has_cost, best=(e.has_cost and e.name == cheapest),
            )
            for e in rows
        ]

    @rx.var(cache=True)
    def my_colleges_count(self) -> int:
        return len([r for r in self.my_colleges if r.has_cost])

    @rx.var(cache=True)
    def fafsa_when(self) -> dict:
        """Where the student is in the FAFSA year, right now.

        Filing late is the most expensive ordinary mistake in this process,
        and the app previously had no idea what month it was."""
        t = fafsa.timeline()
        return {"headline": t.headline, "detail": t.detail,
                "award_year": t.award_year, "phase": t.phase,
                "urgent": t.urgent}

    @rx.var(cache=True)
    def net_price_note(self) -> str:
        return fafsa.NET_PRICE_CALCULATOR_NOTE

    @rx.var(cache=True)
    def sim_experiments(self) -> list[ExpRow]:
        """Each what-if, already run, so the card can say what it would do
        before the student commits to trying it."""
        base = self._household()
        now = fafsa.student_aid_index(base).sai
        out = []
        for x in fafsa.EXPERIMENTS:
            after = fafsa.student_aid_index(fafsa.apply_experiment(base, x.key)).sai
            d = after - now
            if d == 0:
                delta, direction = "no change at all", "flat"
            elif d > 0:
                delta, direction = f"+${d:,} to your SAI", "up"
            else:
                delta, direction = f"-${abs(d):,} off your SAI", "down"
            out.append(ExpRow(key=x.key, label=x.label, teaches=x.teaches,
                              delta=delta, direction=direction))
        return out

    @rx.var(cache=True)
    def sim_headline(self) -> str:
        rows = self.sim_pay
        if not rows:
            return ""
        cheap = rows[0]
        dear = rows[-1]
        if cheap.key.startswith("private") and not dear.key.startswith("private"):
            return (f"With these numbers, the {cheap.name.lower()} is your "
                    f"cheapest option at {cheap.you_pay}, compared with "
                    f"{dear.you_pay}. That's the opposite of what the sticker "
                    f"prices suggest.")
        return (f"The cheapest here is {cheap.name.lower()} at {cheap.you_pay}, "
                f"and the most expensive is {dear.you_pay}. That gap is a good "
                f"reason to apply to a range of schools.")

    @rx.event
    def set_sim(self, field: str, value):
        """One setter for every input — the sliders and the number boxes all
        arrive here, so clamping lives in exactly one place."""
        try:
            v = int(float(value))
        except (TypeError, ValueError):
            return
        limits = {
            "sim_income": (0, 400_000),
            "sim_household": (2, 10),
            "sim_in_college": (1, 5),
            "sim_parent_savings": (0, 500_000),
            "sim_student_income": (0, 40_000),
            "sim_student_savings": (0, 50_000),
        }
        if field not in limits:
            return
        lo, hi = limits[field]
        setattr(self, field, max(lo, min(hi, v)))
        self.sim_touched = True

    @rx.event
    def toggle_single(self):
        self.sim_single = not self.sim_single
        self.sim_touched = True

    @rx.event
    def run_experiment(self, key: str):
        """Actually apply a what-if, so the student can keep playing from it."""
        after = fafsa.apply_experiment(self._household(), key)
        self.sim_income = after.income
        self.sim_household = after.household
        self.sim_in_college = after.in_college
        self.sim_parent_savings = after.parent_savings
        self.sim_student_income = after.student_income
        self.sim_student_savings = after.student_savings
        self.sim_touched = True

    @rx.event
    def reset_sim(self):
        for k, v in (("sim_income", 65_000), ("sim_household", 4),
                     ("sim_in_college", 1), ("sim_parent_savings", 15_000),
                     ("sim_student_income", 3_000), ("sim_student_savings", 1_200)):
            setattr(self, k, v)
        self.sim_single = False
        self.sim_touched = False

    @rx.var
    def is_checklist(self) -> bool:
        return self.tab == "checklist"

    @rx.var
    def is_simulator(self) -> bool:
        return self.tab == "simulator"

    @rx.var
    def is_costs(self) -> bool:
        return self.tab == "costs"

    @rx.var
    def is_scholarships(self) -> bool:
        return self.tab == "scholarships"

    @rx.var
    def is_learn(self) -> bool:
        return self.tab == "learn"

    @rx.var(deps=["done_count", "step_total"])
    def checklist_line(self) -> str:
        if self.done_count == 0:
            return "Nothing checked off yet. The first one takes about five minutes."
        if self.done_count >= self.step_total:
            return "Every step is done. That's all the paperwork."
        return f"{self.done_count} of {self.step_total} steps done."

    @rx.var(deps=["priced", "total_schools", "cheapest"])
    def cost_line(self) -> str:
        if self.total_schools == 0:
            return "Add colleges to your list and their costs show up here."
        if self.priced == 0:
            return (("No costs added yet. Every US college has a net price calculator on "
                     "its website. Start there."))
        if self.priced == 1:
            return f"{self.cheapest} is the only one priced so far."
        return f"{self.cheapest} is the cheapest so far, at {self.cheapest_net}."

    # ---------------------------------------------------------------- load
    @rx.event
    async def load(self):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        self._refresh(uid)
        self.loading = False

    def _refresh(self, uid: int) -> None:
        today = utcnow().date()
        with db.get_session() as s:
            done = aid.done_keys(s, uid)
            cs = aid.costs(s, uid)
            fl = aid.flags(s, uid, cs)
            summary = aid.summary(s, uid, cs)
            rows = list(s.exec(select(Scholarship)
                               .where(Scholarship.user_id == uid)).all())
            new = achievements.award(s, uid)

        self.just_earned = new[0]["title"] if new else ""

        self.steps = [
            StepRow(key=st["key"], phase=st["phase"], title=st["title"],
                    detail=st["detail"], xp=st["xp"], done=st["key"] in done)
            for st in content.STEPS
        ]
        self.phases = list(content.PHASES)
        self.step_total = len(content.STEPS)
        self.done_count = sum(1 for st in self.steps if st.done)
        self.checklist_percent = aid.checklist_percent(done)

        dearest = max((c.net for c in cs if c.net is not None), default=0) or 1
        self.cost_rows = [
            CostRow(id=c.school_id, name=c.name,
                    sticker=aid.fmt(c.sticker), aid=aid.fmt(c.aid),
                    net=aid.fmt(c.net), known=c.known,
                    round_name=c.round_name, binding=c.binding,
                    needs_css=c.needs_css, aid_deadline=c.aid_deadline,
                    bar=int(round(100 * (c.net or 0) / dearest)) if c.known else 0)
            for c in cs
        ]
        self.flag_rows = [FlagRow(level=f.level, title=f.title, detail=f.detail)
                          for f in fl]

        rows.sort(key=lambda r: (r.deadline is None,
                                 r.deadline or utcnow(), r.name.lower()))
        self.scholarships = [
            SchRow(id=r.id, name=r.name,
                   amount=aid.fmt(aid.money(r.amount)),
                   deadline=r.deadline.strftime("%b %d") if r.deadline else "",
                   deadline_iso=r.deadline.strftime("%Y-%m-%d") if r.deadline else "",
                   status=content.STATUSES.get(r.status, r.status),
                   status_key=r.status, url=r.url or "",
                   days=(r.deadline.date() - today).days if r.deadline else 0,
                   urgent=bool(r.deadline and 0 <= (r.deadline.date() - today).days <= 14
                               and r.status in ("found", "started")))
            for r in rows
        ]

        self.glossary = [Term(word=w, meaning=m) for w, m in content.GLOSSARY]

        self.priced = summary["priced"]
        self.total_schools = summary["total"]
        self.cheapest = summary["cheapest"]
        self.cheapest_net = summary["cheapest_net"]
        self.spread = summary["spread"]
        self.won = summary["won"]
        self.chasing = summary["chasing"]

    # ------------------------------------------------------------ actions
    @rx.event
    def set_tab(self, tab: str):
        # Whitelisted rather than assigned straight through: `tab` reaches
        # this from the client, and an unknown value would render an empty
        # screen with no tab looking selected.
        known = ("checklist", "simulator", "costs", "scholarships", "learn")
        self.tab = tab if tab in known else "checklist"

    @rx.event
    async def toggle_step(self, key: str):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        with db.get_session() as s:
            aid.toggle(s, uid, key)
        self._refresh(uid)

    @rx.event
    def toggle_school(self, school_id: int):
        self.open_school = 0 if self.open_school == school_id else school_id

    @rx.event
    async def set_money(self, school_id: int, field: str, value: str):
        """Sticker, aid offered, or the net price straight off a calculator."""
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        if field not in ("sticker", "aid_offered", "net_cost"):
            return
        with db.get_session() as s:
            row = s.get(School, school_id)
            if row and row.user_id == uid:   # never trust an id from the client
                setattr(row, field, (value or "").strip()[:40] or None)
                s.add(row); s.commit()
        self._refresh(uid)

    @rx.event
    async def set_round(self, school_id: int, value: str):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        if value not in content.ROUNDS:
            return
        with db.get_session() as s:
            row = s.get(School, school_id)
            if row and row.user_id == uid:
                row.round = value
                s.add(row); s.commit()
        self._refresh(uid)

    @rx.event
    async def toggle_css(self, school_id: int):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        with db.get_session() as s:
            row = s.get(School, school_id)
            if row and row.user_id == uid:
                row.needs_css = not row.needs_css
                s.add(row); s.commit()
        self._refresh(uid)

    @rx.event
    async def set_aid_deadline(self, school_id: int, value: str):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        when = None
        if value:
            try:
                when = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                self.error = "That date didn't make sense."
                return
        with db.get_session() as s:
            row = s.get(School, school_id)
            if row and row.user_id == uid:
                row.aid_deadline = when
                s.add(row); s.commit()
        self.error = ""
        self._refresh(uid)

    # ------------------------------------------------------- scholarships
    @rx.event
    async def add_scholarship(self, form: dict):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        name = (form.get("name") or "").strip()
        if not name:
            self.error = "Give it a name first."
            return
        when = None
        raw = (form.get("deadline") or "").strip()
        if raw:
            try:
                when = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                when = None
        with db.get_session() as s:
            s.add(Scholarship(user_id=uid, name=name[:140],
                              amount=(form.get("amount") or "").strip()[:40] or None,
                              url=(form.get("url") or "").strip()[:300],
                              deadline=when))
            s.commit()
        self.error = ""
        self._refresh(uid)

    @rx.event
    async def set_scholarship_status(self, sid: int, status: str):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        if status not in content.STATUSES:
            return
        with db.get_session() as s:
            row = s.get(Scholarship, sid)
            if row and row.user_id == uid:
                row.status = status
                s.add(row); s.commit()
        self._refresh(uid)

    @rx.event
    async def remove_scholarship(self, sid: int):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        with db.get_session() as s:
            row = s.get(Scholarship, sid)
            if row and row.user_id == uid:
                s.delete(row); s.commit()
        self._refresh(uid)

    @rx.event
    def dismiss_earned(self):
        self.just_earned = ""
