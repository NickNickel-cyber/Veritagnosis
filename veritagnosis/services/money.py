"""
Paying for it: the Student Aid Index model, Pell, what colleges
would actually cost this family, and the aid paperwork.

Merged from: fafsa, aid.
"""
from __future__ import annotations

import dataclasses
import re
from sqlmodel import Session, select
from veritagnosis.content import aid as content
from veritagnosis.models import AidTask, School, Scholarship, utcnow


# ====================================================================
# fafsa
# ====================================================================

PELL_MAX = 7395          # 2026-27 award year
PELL_MIN = 740           # 10% of the maximum, rounded to the nearest $5
PELL_SAI_CUTOFF = 14790  # twice the maximum: at or above this, no Pell at all
AWARD_YEAR = "2026-27"

# HHS poverty guideline, 48 contiguous states and DC, 2025.
# FPL(n) = 15650 + 5500 * (n - 1)
FPL_BASE = 15650
FPL_STEP = 5500

# Pell thresholds, as a multiple of the poverty guideline, for a DEPENDENT
# student. Single-parent households get the more generous line.
MAX_PELL_FPL = {"single": 2.25, "two": 1.75}
MIN_PELL_FPL = {"single": 3.25, "two": 2.75}

# --------------------------------------------------------------- simplified
# Everything below this line is an approximation of the federal formula.

# Income the family is not expected to touch, by household size. The real
# table is finer; this is the shape of it.
INCOME_PROTECTION = {2: 24_000, 3: 30_000, 4: 37_000, 5: 43_500, 6: 50_500}
INCOME_PROTECTION_STEP = 6_500

# Rough federal+state+payroll take. The real formula uses taxes actually paid.
TAX_ALLOWANCE_RATE = 0.17

# Savings a family keeps before any of it counts.
ASSET_PROTECTION = 10_000
PARENT_ASSET_RATE = 0.12

# The student's own money is hit far harder than the parents' — worth seeing.
STUDENT_INCOME_PROTECTION = 11_130
STUDENT_INCOME_RATE = 0.50
STUDENT_ASSET_RATE = 0.20

# Progressive bands on what is left of parent income, mirroring the federal
# schedule's climb to 47%.
AAI_BANDS = [(18_000, 0.22), (23_000, 0.25), (28_000, 0.29),
             (33_000, 0.34), (38_000, 0.40)]
AAI_TOP_RATE = 0.47

# The floor is real: the SAI can go negative, which signals deeper need.
SAI_FLOOR = -1500


def poverty_line(household: int) -> int:
    """The HHS guideline for a household of this size."""
    return FPL_BASE + FPL_STEP * (max(1, household) - 1)


def income_protection(household: int) -> int:
    n = max(2, household)
    if n in INCOME_PROTECTION:
        return INCOME_PROTECTION[n]
    biggest = max(INCOME_PROTECTION)
    return INCOME_PROTECTION[biggest] + INCOME_PROTECTION_STEP * (n - biggest)


def _assess(available: float) -> float:
    """Walk the progressive bands. Only what is above each band is taxed at
    the next rate, which is why a raise never costs a family more than it
    gains — a thing people genuinely fear and should not."""
    if available <= 0:
        return 0.0
    total, last = 0.0, 0
    for ceiling, rate in AAI_BANDS:
        if available <= last:
            return total
        slice_ = min(available, ceiling) - last
        total += slice_ * rate
        last = ceiling
    if available > last:
        total += (available - last) * AAI_TOP_RATE
    return total


@dataclasses.dataclass
class Household:
    """What a student can actually answer without ringing an accountant."""

    income: int = 65_000            # parent AGI
    household: int = 4              # people in the household
    in_college: int = 1             # including the student
    single_parent: bool = False
    parent_savings: int = 15_000    # NOT retirement, NOT the house
    student_income: int = 3_000
    student_savings: int = 1_200


@dataclasses.dataclass
class Result:
    sai: int
    pell: int
    parent_income_part: int
    parent_asset_part: int
    student_income_part: int
    student_asset_part: int
    pell_basis: str                 # why Pell came out the way it did
    poverty_line: int
    pct_of_poverty: int


def student_aid_index(h: Household) -> Result:
    """The whole calculation, with its parts kept separate.

    The parts are returned rather than just the total because the parts are
    the lesson: seeing that the asset contribution is a few hundred dollars
    while the income contribution is several thousand is what corrects the
    belief that savings are what disqualify you.
    """
    # --- parents' income
    allowances = income_protection(h.household) + h.income * TAX_ALLOWANCE_RATE
    available = max(0.0, h.income - allowances)

    # --- parents' assets. The house and every retirement account are absent
    # from this line on purpose: FAFSA does not ask about them.
    #
    # Savings do NOT go straight onto the total. 12% of what is left after the
    # protection allowance is added to available income, and the *sum* is what
    # gets assessed. That routing is the reason savings barely register: a
    # dollar saved reaches the SAI as twelve cents, and only then is that
    # twelve cents taxed at the band rate. Adding the 12% to the total
    # directly — which is the obvious way to write it — overstates the damage
    # done by savings several times over, and savings are exactly what
    # families wrongly believe disqualifies them.
    countable = max(0, h.parent_savings - ASSET_PROTECTION)
    from_assets = countable * PARENT_ASSET_RATE

    parent_total = _assess(available + from_assets)
    parent_income_part = _assess(available)
    parent_asset_part = parent_total - parent_income_part

    # --- the student's own money, assessed much harder
    student_income_part = max(
        0.0, (h.student_income - STUDENT_INCOME_PROTECTION)) * STUDENT_INCOME_RATE
    student_asset_part = max(0, h.student_savings) * STUDENT_ASSET_RATE

    total = (parent_income_part + parent_asset_part
             + student_income_part + student_asset_part)

    # Before 2024 this was divided by the number in college. It is not any
    # more, and that single change is why some families are suddenly asked
    # for far more than an older sibling was.
    sai = int(round(max(SAI_FLOOR, total)))

    pell, basis = pell_award(h, sai)
    line = poverty_line(h.household)
    return Result(
        sai=sai,
        pell=pell,
        parent_income_part=int(round(parent_income_part)),
        parent_asset_part=int(round(parent_asset_part)),
        student_income_part=int(round(student_income_part)),
        student_asset_part=int(round(student_asset_part)),
        pell_basis=basis,
        poverty_line=line,
        pct_of_poverty=int(round(100 * h.income / line)) if line else 0,
    )


def pell_award(h: Household, sai: int) -> tuple[int, str]:
    """Pell, and the reason for it.

    Three doors, checked in order, exactly as the federal rules do it: under
    the generous poverty multiple you get the maximum regardless of the SAI;
    under the higher multiple you get at least the minimum; otherwise the
    award is the maximum less your SAI.
    """
    kind = "single" if h.single_parent else "two"
    line = poverty_line(h.household)
    max_line = line * MAX_PELL_FPL[kind]
    min_line = line * MIN_PELL_FPL[kind]

    if h.income <= max_line:
        return PELL_MAX, (
            f"Household income is under {MAX_PELL_FPL[kind]:g}x the poverty "
            f"line for {h.household} people, so the maximum Pell applies "
            f"whatever the SAI works out to.")
    if sai >= PELL_SAI_CUTOFF:
        return 0, (f"An SAI of {sai:,} is at or above {PELL_SAI_CUTOFF:,}, "
                   f"which is the point where Pell stops entirely.")
    if h.income <= min_line:
        return PELL_MIN, (
            f"Household income is under {MIN_PELL_FPL[kind]:g}x the poverty "
            f"line, which guarantees at least the minimum Pell.")

    calculated = PELL_MAX - sai
    if calculated < PELL_MIN:
        return 0, (f"The maximum Pell less an SAI of {sai:,} comes to under "
                   f"the {PELL_MIN:,} minimum, so no Pell this year. Every "
                   f"other kind of aid is still open.")
    return int(round(calculated / 5) * 5), (
        f"Pell here is the maximum ({PELL_MAX:,}) less your SAI ({sai:,}).")


# ------------------------------------------------------------------ colleges
@dataclasses.dataclass
class Archetype:
    key: str
    name: str
    blurb: str
    cost: int
    meets: int          # percent of demonstrated need the college actually meets


# Illustrative, and labelled as such wherever they are shown. The spread
# between them is the point: the dearest one is frequently the cheapest.
ARCHETYPES = [
    Archetype("public_in", "State school, in state",
              "Your own state's public university.", 29_000, 60),
    Archetype("public_out", "State school, out of state",
              "The same kind of place, one state over. Rarely worth the gap.",
              48_000, 45),
    Archetype("private_ok", "Private, ordinary endowment",
              "A private college without a famous endowment.", 62_000, 70),
    Archetype("private_rich", "Private, meets full need",
              "The wealthy ones. High sticker, and they cover the gap.",
              85_000, 100),
]


@dataclasses.dataclass
class Estimate:
    key: str
    name: str
    blurb: str
    cost: int
    need: int
    met: int
    pell: int
    you_pay: int
    meets: int


def what_you_would_pay(result: Result, colleges=None) -> list[Estimate]:
    """Run the SAI against each college. Cheapest first, because the ranking
    is usually the surprise."""
    out = []
    for c in (colleges or ARCHETYPES):
        need = max(0, c.cost - result.sai)
        met = int(round(need * c.meets / 100))
        # Pell is federal and comes regardless of how generous the college is,
        # but it cannot pay for more than the need that exists.
        pell = min(result.pell, max(0, need - met))
        you_pay = max(0, c.cost - met - pell)
        out.append(Estimate(key=c.key, name=c.name, blurb=c.blurb, cost=c.cost,
                            need=need, met=met, pell=pell, you_pay=you_pay,
                            meets=c.meets))
    out.sort(key=lambda e: e.you_pay)
    return out


# ------------------------------------------------------------- experiments
@dataclasses.dataclass
class Experiment:
    key: str
    label: str
    teaches: str


EXPERIMENTS = [
    Experiment("retire",
               "Move $20,000 of savings into a retirement account",
               "Retirement accounts are invisible to FAFSA. The same money, "
               "in a different pot, stops counting."),
    Experiment("sibling",
               "A second sibling starts college",
               "Before 2024 this roughly halved the family contribution. It "
               "no longer does, and that is the change that catches families "
               "who are planning from an older sibling's experience."),
    Experiment("raise",
               "A $10,000 raise at home",
               "Income moves the number far more than savings do. This is "
               "the lever that actually matters."),
    Experiment("student_savings",
               "The student saves $5,000 from a job",
               "A student's own savings are assessed at 20%, against 12% for "
               "the parents' — the harshest rate in the formula. Money in a "
               "parent's name counts for less."),
]


def apply_experiment(h: Household, key: str) -> Household:
    """A copy of the household with one thing changed."""
    n = dataclasses.replace(h)
    if key == "retire":
        n.parent_savings = max(0, h.parent_savings - 20_000)
    elif key == "sibling":
        n.in_college = h.in_college + 1
        n.household = max(h.household, h.in_college + 2)
    elif key == "raise":
        n.income = h.income + 10_000
    elif key == "student_savings":
        n.student_savings = h.student_savings + 5_000
    return n


if __name__ == "__main__":
    for income in (35_000, 65_000, 120_000, 250_000):
        h = Household(income=income)
        r = student_aid_index(h)
        print(f"\nincome {income:>8,}  SAI {r.sai:>7,}  Pell {r.pell:>6,}"
              f"  ({r.pct_of_poverty}% of the poverty line)")
        print(f"   {r.pell_basis}")
        for e in what_you_would_pay(r):
            print(f"     {e.name:<34} sticker {e.cost:>7,} -> you pay {e.you_pay:>7,}")


# =====================================================================
# Your own list, not four made-up colleges
# =====================================================================
#
# Everything above runs the SAI against four illustrative archetypes. That
# teaches the shape, but the student is sitting there with a real list, and
# the question they actually have is "what would MY schools cost me".
#
# content/colleges.py carries a real, cited sticker price for each college we
# have data for, so need (cost minus SAI) is honest arithmetic on honest
# inputs and can simply be shown.
#
# What we deliberately do NOT have is each college's "percent of demonstrated
# need met" — the figure that decides what you finally pay. It ranges from
# about 40% to 100% between institutions and we have not sourced it. Inventing
# it would produce a confident dollar figure that could be wrong by tens of
# thousands, aimed at a family deciding whether college is affordable. So
# instead of one fabricated number this returns a RANGE across the plausible
# spread, labelled as a range, and points at the one place that gives a real
# answer: that college's own net price calculator.

# The observed spread of "percent of need met" across US institutions. Used to
# bound the range, never to predict where a particular college sits.
NEED_MET_LOW = 60
NEED_MET_HIGH = 100

NET_PRICE_CALCULATOR_NOTE = (
    "Every US college is required by law to host a net price calculator. "
    "That is the only thing that gives you a real number for a real college — "
    "this is arithmetic to get you oriented before you go and use one."
)


@dataclasses.dataclass
class RealEstimate:
    """One college from the student's own list, priced against their SAI."""

    name: str
    cost: int                   # published sticker, cited
    need: int                   # cost - SAI, honest arithmetic
    pell: int
    pay_if_generous: int        # if the college meets 100% of need
    pay_if_typical: int         # if it meets NEED_MET_LOW
    data_year: str
    source_url: str
    confidence: str
    has_cost: bool


def price_your_list(result: "Result", schools) -> list[RealEstimate]:
    """Run the SAI against the student's actual colleges.

    `schools` is any iterable of objects with a `.name`. Colleges we have no
    published cost for come back with has_cost False rather than a guess, so
    the screen can say so instead of quietly leaving them out — a missing
    college is information too.

    Sorted by the optimistic figure, because the ranking is the lesson: an
    expensive college that meets full need routinely costs a family less than
    a cheap one that does not.
    """
    from veritagnosis.content.colleges import BY_NAME

    out: list[RealEstimate] = []
    for sc in schools:
        entry = BY_NAME.get((getattr(sc, "name", "") or "").strip().lower())
        if entry is None or not entry.get("cost_year"):
            out.append(RealEstimate(
                name=getattr(sc, "name", ""), cost=0, need=0, pell=0,
                pay_if_generous=0, pay_if_typical=0, data_year="",
                source_url="", confidence="", has_cost=False))
            continue

        cost = int(entry["cost_year"])
        need = max(0, cost - result.sai)

        # Pell is federal and arrives whatever the college does, but it cannot
        # pay for need that does not exist.
        def _pay(meets_pct: int) -> int:
            met = int(round(need * meets_pct / 100))
            pell = min(result.pell, max(0, need - met))
            return max(0, cost - met - pell)

        out.append(RealEstimate(
            name=entry["name"],
            cost=cost,
            need=need,
            pell=min(result.pell, need),
            pay_if_generous=_pay(NEED_MET_HIGH),
            pay_if_typical=_pay(NEED_MET_LOW),
            data_year=entry.get("data_year", ""),
            source_url=entry.get("source_url", ""),
            confidence=entry.get("confidence", ""),
            has_cost=True,
        ))

    out.sort(key=lambda e: (not e.has_cost, e.pay_if_generous))
    return out


# =====================================================================
# Where you are in the FAFSA year
# =====================================================================
#
# The form opens on 1 October for the following academic year, and the single
# most expensive mistake in the whole process is filing late — several states
# and many colleges award their own aid first-come-first-served until the
# money is gone, which means an identical family filing in March gets less
# than one filing in October. Nothing in the app knew what month it was, so it
# could not say any of that at the moment it mattered.

FAFSA_OPENS_MONTH = 10
FAFSA_OPENS_DAY = 1
FEDERAL_DEADLINE_MONTH = 6      # 30 June, after the award year ends


@dataclasses.dataclass
class Timeline:
    award_year: str
    phase: str          # before_open | open_early | open_late | closing
    headline: str
    detail: str
    urgent: bool


def timeline(today=None) -> Timeline:
    """What the calendar means for this student, right now."""
    import datetime as _dt

    today = today or _dt.date.today()
    y = today.year

    # The cycle that opened most recently: October of this year if we are past
    # 1 October, otherwise October of last year.
    opened = _dt.date(y, FAFSA_OPENS_MONTH, FAFSA_OPENS_DAY)
    if today < opened:
        cycle_start = _dt.date(y - 1, FAFSA_OPENS_MONTH, FAFSA_OPENS_DAY)
    else:
        cycle_start = opened
    award = f"{cycle_start.year + 1}-{str(cycle_start.year + 2)[2:]}"

    days_to_open = (opened - today).days
    if 0 < days_to_open <= 60:
        return Timeline(
            award_year=f"{y + 1}-{str(y + 2)[2:]}",
            phase="before_open",
            headline=f"FAFSA opens in {days_to_open} days.",
            detail=("Filing in the first weeks matters more than most people "
                    "realise: several states and many colleges hand out their "
                    "own aid until it runs out, so the same family filing in "
                    "October can get more than one filing in March. Get your "
                    "tax return and account details together now."),
            urgent=False,
        )

    weeks_open = (today - cycle_start).days // 7
    if weeks_open <= 8:
        return Timeline(
            award_year=award, phase="open_early",
            headline=f"FAFSA for {award} is open — this is the best time to file.",
            detail=("You are inside the window where first-come aid is still "
                    "available. This is the single cheapest thing you can do "
                    "for your own finances this year."),
            urgent=True,
        )
    if weeks_open <= 26:
        return Timeline(
            award_year=award, phase="open_late",
            headline=f"FAFSA for {award} is open, and state money is going.",
            detail=("Many state deadlines have passed or are close. File now "
                    "rather than waiting for admissions decisions — you do "
                    "not need to know where you are going to submit it."),
            urgent=True,
        )
    return Timeline(
        award_year=award, phase="closing",
        headline=f"The {award} FAFSA is still open, and late is far better than never.",
        detail=("Most state and institutional money for this year is gone, "
                "but federal aid including Pell is not first-come — it is "
                "still worth filing."),
        urgent=True,
    )


# ====================================================================
# aid
# ====================================================================

_NUM = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def money(text: str | None) -> float | None:
    """Read a number out of whatever a person typed, or None.

    Deliberately returns None rather than 0 for junk: zero is a real answer
    ("this college would cost me nothing") and must not be confused with "we
    could not read this".
    """
    if text is None:
        return None
    t = str(text).strip().lower().replace("$", "").replace(" ", "")
    if not t:
        return None
    mult = 1.0
    if t.endswith("k"):
        mult, t = 1000.0, t[:-1]
    m = _NUM.search(t)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "")) * mult
    except ValueError:
        return None


def fmt(value: float | None) -> str:
    if value is None:
        return "—"
    return f"${value:,.0f}"


@dataclasses.dataclass
class Cost:
    """What one college would actually cost."""

    school_id: int
    name: str
    sticker: float | None
    aid: float | None
    net: float | None          # what you would pay
    known: bool                # enough typed in to be worth comparing
    round: str
    round_name: str
    binding: bool
    needs_css: bool
    aid_deadline: str
    aid_days: int | None


def school_cost(s: School) -> Cost:
    sticker = money(s.sticker)
    aid = money(s.aid_offered)
    typed_net = money(s.net_cost)

    # A net cost typed in directly wins: it came from a real offer letter or a
    # net price calculator, and both are better than our subtraction.
    if typed_net is not None:
        net = typed_net
    elif sticker is not None and aid is not None:
        net = max(0.0, sticker - aid)
    elif sticker is not None:
        net = sticker
    else:
        net = None

    days = None
    if s.aid_deadline is not None:
        days = (s.aid_deadline.date() - utcnow().date()).days

    return Cost(
        school_id=s.id, name=s.name, sticker=sticker, aid=aid, net=net,
        known=net is not None,
        round=s.round or "regular",
        round_name=content.ROUNDS.get(s.round or "regular", "Regular Decision"),
        binding=(s.round or "regular") in content.BINDING,
        needs_css=bool(s.needs_css),
        aid_deadline=s.aid_deadline.strftime("%b %d") if s.aid_deadline else "",
        aid_days=days,
    )


def costs(session: Session, user_id: int) -> list[Cost]:
    rows = list(session.exec(select(School).where(School.user_id == user_id)).all())
    out = [school_cost(s) for s in rows]
    # Cheapest known first — that is the comparison the screen exists to make.
    out.sort(key=lambda c: (not c.known, c.net if c.net is not None else 0))
    return out


# --------------------------------------------------------------------------
# Things worth noticing
# --------------------------------------------------------------------------

@dataclasses.dataclass
class Flag:
    level: str      # warn | info
    title: str
    detail: str


def flags(session: Session, user_id: int, cs: list[Cost]) -> list[Flag]:
    """The handful of situations that quietly cost people money."""
    out: list[Flag] = []

    binding = [c for c in cs if c.binding]
    if len(binding) > 1:
        out.append(Flag(
            "warn", "Two binding applications",
            f"{', '.join(c.name for c in binding)} are all marked Early "
            f"Decision. ED is a commitment to attend if admitted, so you can "
            f"only hold one. Change the others before you send them."))
    elif len(binding) == 1:
        out.append(Flag(
            "info", f"{binding[0].name} is binding",
            "Early Decision commits you to attend if you are admitted, which "
            "means accepting before you can compare aid offers. If cost will "
            "decide where you go, that is worth talking through with your "
            "counsellor first."))

    css = [c for c in cs if c.needs_css]
    if css:
        out.append(Flag(
            "info", f"{len(css)} " + ("college needs" if len(css) == 1 else
                                      "colleges need") + " a CSS Profile",
            ", ".join(c.name for c in css) + ". It is a separate form from the "
            "FAFSA with its own deadline, usually earlier than you expect."))

    soon = [c for c in cs if c.aid_days is not None and 0 <= c.aid_days <= 21]
    if soon:
        nearest = min(soon, key=lambda c: c.aid_days)
        out.append(Flag(
            "warn", "An aid deadline is close",
            f"{nearest.name} closes in {nearest.aid_days} "
            f"{'day' if nearest.aid_days == 1 else 'days'}. Aid deadlines are "
            f"often separate from the application deadline and are frequently "
            f"the earlier of the two."))

    passed = [c for c in cs if c.aid_days is not None and c.aid_days < 0]
    if passed:
        out.append(Flag(
            "warn", "An aid deadline has gone by",
            f"{', '.join(c.name for c in passed)}. Ring the financial aid "
            f"office anyway — late is not always closed, and they would rather "
            f"tell you than have you assume."))

    unknown = [c for c in cs if not c.known]
    if unknown and len(unknown) == len(cs):
        out.append(Flag(
            "info", "No costs recorded yet",
            "Run each college's net price calculator — every US college has to "
            "publish one — and put the estimate in here. Sticker prices are "
            "usually nothing like what a family actually pays."))

    return out


def summary(session: Session, user_id: int, cs: list[Cost] | None = None) -> dict:
    if cs is None:
        cs = costs(session, user_id)
    known = [c for c in cs if c.known and c.net is not None]

    sch = list(session.exec(
        select(Scholarship).where(Scholarship.user_id == user_id)).all())
    won = sum(money(s.amount) or 0 for s in sch if s.status == "won")
    chasing = sum(money(s.amount) or 0 for s in sch
                  if s.status in ("found", "started", "submitted"))

    return {
        "priced": len(known),
        "total": len(cs),
        "cheapest": known[0].name if known else "",
        "cheapest_net": fmt(known[0].net) if known else "—",
        "dearest_net": fmt(known[-1].net) if known else "—",
        "spread": fmt(known[-1].net - known[0].net) if len(known) > 1 else "—",
        "scholarships": len(sch),
        "won": fmt(won) if won else "—",
        "chasing": fmt(chasing) if chasing else "—",
    }


# --------------------------------------------------------------------------
# The checklist
# --------------------------------------------------------------------------

def done_keys(session: Session, user_id: int) -> set[str]:
    return {r.task_key for r in session.exec(
        select(AidTask).where(AidTask.user_id == user_id)).all()}


def toggle(session: Session, user_id: int, key: str) -> bool:
    """Tick or untick a step. Returns whether it is now done.

    Unticking has to be possible: someone will tap the wrong row, and a
    checklist you cannot correct is a checklist people stop trusting.
    """
    if key not in {s["key"] for s in content.STEPS}:
        return False
    row = session.exec(
        select(AidTask).where(AidTask.user_id == user_id,
                              AidTask.task_key == key)).first()
    if row:
        session.delete(row)
        session.commit()
        return False
    session.add(AidTask(user_id=user_id, task_key=key, done_at=utcnow()))
    session.commit()
    return True


def checklist_percent(done: set[str]) -> int:
    total = len(content.STEPS) or 1
    return int(round(100 * len(done & {s["key"] for s in content.STEPS}) / total))
