"""
Paying for college.

Four tabs, in the order the year actually happens: the paperwork checklist,
then what each college would really cost, then the scholarships, then the words
nobody explains.

The disclaimer at the top is not decoration and is not there to cover anyone.
It is the honest limit: a program can hold the checklist and do the
subtraction, and it cannot know a family's situation. Saying so plainly is more
useful than pretending otherwise, and it points at the two people who can
actually help — the school counsellor and the college's own aid office.
"""

from __future__ import annotations

import reflex as rx

from veritagnosis.content import aid as content
from veritagnosis.services import money as fafsa
from veritagnosis.states.money_state import AidState
from veritagnosis.ui.theme import btn, error_box, shell

ROUND_OPTIONS = [(k, v) for k, v in content.ROUNDS.items()]
SCH_STATUS = [(k, v) for k, v in content.STATUSES.items()]


def _tabs() -> rx.Component:
    return rx.box(
        *[
            rx.el.button(
                label, type="button",
                custom_attrs={"aria-selected": AidState.tab == key},
                on_click=AidState.set_tab(key),
            )
            for key, label in [("checklist", "Paperwork"),
                               ("simulator", "What would I pay?"),
                               ("costs", "What it costs"),
                               ("scholarships", "Scholarships"), ("learn", "The words")]
        ],
        class_name="tabrow",
    )


def _step(st) -> rx.Component:
    return rx.box(
        rx.el.button(
            rx.box(rx.cond(st.done, "✓", "○"), class_name="st-mark"),
            rx.box(
                rx.box(
                    rx.el.span(st.title, class_name="st-label"),
                    rx.el.span("+", st.xp, " xp", class_name="st-detail"),
                    class_name="st-head",
                ),
                rx.box(st.detail, class_name="st-hint"),
                class_name="st-main",
            ),
            type="button", class_name="st-btn",
            on_click=AidState.toggle_step(st.key),
        ),
        class_name=rx.cond(st.done, "st done", "st"),
    )


def _phase_block(phase) -> rx.Component:
    return rx.box(
        rx.box(phase, class_name="note-tag"),
        rx.foreach(
            AidState.steps,
            lambda st: rx.cond(st.phase == phase, _step(st), rx.fragment()),
        ),
        class_name="aid-phase",
    )


def _form_card(f: dict) -> rx.Component:
    """One of the two forms, explained. Static content, so a plain loop."""
    return rx.box(
        rx.box(
            rx.el.strong(f["name"]),
            rx.el.span(f["full"], class_name="faint tiny"),
            class_name="fm-head",
        ),
        rx.box(rx.el.b("Who needs it. "), f["who"], class_name="fm-line"),
        rx.box(rx.el.b("What it costs. "), f["cost"], class_name="fm-line"),
        rx.box(rx.el.b("When. "), f["when"], class_name="fm-line"),
        rx.box(rx.el.b("Watch out. "), f["watch"], class_name="fm-line"),
        rx.box(
            rx.el.a("Check the official dates →", href=f["verify"],
                    target="_blank", rel="noopener noreferrer",
                    class_name="st-go"),
            class_name="fm-line",
        ),
        class_name="card fm",
    )


def _checklist() -> rx.Component:
    return rx.box(
        rx.box(
            rx.text(AidState.checklist_line, class_name="rp-line"),
            rx.box(rx.el.i(style={"width": AidState.checklist_percent.to_string() + "%"}),
                   class_name="cp-bar", style={"maxWidth": "none"}),
            class_name="card report",
        ),
        rx.foreach(AidState.phases, _phase_block),
        rx.heading("The two forms", size="4", style={"marginTop": "var(--s6)"}),
        *[_form_card(f) for f in content.FORMS],
        rx.heading("Traps", size="4", style={"marginTop": "var(--s6)"}),
        *[
            rx.box(
                rx.box(t, class_name="note-tag"),
                rx.text(d),
                class_name="card note",
                style={"marginTop": "var(--s3)"},
            )
            for t, d in content.TRAPS
        ],
    )


def _dial(label: str, field: str, value, lo: int, hi: int, step: int,
          shown, hint: str = "") -> rx.Component:
    """One labelled slider. The number is echoed beside the label so the
    student reads a figure rather than a position on a track."""
    return rx.box(
        rx.box(
            rx.el.span(label, class_name="sim-dial-label"),
            rx.el.span(shown, class_name="sim-dial-value"),
            class_name="sim-dial-head",
        ),
        rx.el.input(
            type="range", class_name="sim-range",
            min=str(lo), max=str(hi), step=str(step),
            value=value.to_string(),
            on_change=lambda v: AidState.set_sim(field, v),
        ),
        rx.cond(hint != "", rx.box(hint, class_name="sim-dial-hint"), rx.fragment()),
        class_name="sim-dial",
    )


def _sim_inputs() -> rx.Component:
    return rx.box(
        rx.box("Your household", class_name="note-tag"),
        _dial("Household income before tax", "sim_income", AidState.sim_income,
              0, 400000, 1000, AidState.sim_income_label,
              "What the people who support you earn in a year, combined."),
        _dial("People in the household", "sim_household", AidState.sim_household,
              2, 10, 1, AidState.sim_household.to_string()),
        _dial("People in college at once", "sim_in_college", AidState.sim_in_college,
              1, 5, 1, AidState.sim_in_college.to_string(),
              ("Count yourself. This used to lower what you're expected to pay, but "
               "it doesn't anymore.")),
        _dial("Parents' savings and investments", "sim_parent_savings",
              AidState.sim_parent_savings, 0, 300000, 1000,
              AidState.sim_parent_savings_label,
              ("Don't include your home or retirement accounts. FAFSA doesn't ask "
               "about either.")),
        _dial("What you earn yourself", "sim_student_income",
              AidState.sim_student_income, 0, 40000, 500,
              AidState.sim_student_income_label),
        _dial("What you have saved yourself", "sim_student_savings",
              AidState.sim_student_savings, 0, 50000, 250,
              AidState.sim_student_savings_label),
        rx.box(
            rx.el.button(
                rx.cond(AidState.sim_single, "✓  One parent household",
                        "One parent household"),
                type="button",
                class_name=rx.cond(AidState.sim_single,
                                   "btn btn-secondary is-on", "btn btn-secondary"),
                on_click=AidState.toggle_single),
            rx.el.button("Reset", type="button", class_name="btn btn-ghost",
                         on_click=AidState.reset_sim),
            class_name="sim-toggles",
        ),
        class_name="card sim-inputs",
    )


def _sim_result() -> rx.Component:
    return rx.box(
        rx.box(
            rx.box(
                rx.box("YOUR STUDENT AID INDEX", class_name="rp-lbl"),
                rx.box(AidState.sim["sai"], class_name="sim-big"),
                rx.box("Colleges subtract this from their cost to find your need.",
                       class_name="sim-under"),
                class_name="sim-figure",
            ),
            rx.box(
                rx.box("FEDERAL PELL GRANT", class_name="rp-lbl"),
                rx.box(AidState.sim["pell"], class_name="sim-big sim-big-good"),
                rx.box("It's a grant, so there's nothing to pay back.",
                       class_name="sim-under"),
                class_name="sim-figure",
            ),
            class_name="sim-figures",
        ),
        rx.box(AidState.sim["basis"], class_name="sim-basis"),
        class_name="card report sim-result",
    )


def _sim_parts() -> rx.Component:
    return rx.box(
        rx.heading("Where that number comes from", size="4",
                   style={"marginTop": "var(--s6)"}),
        rx.text(("It's four amounts added together. Change the inputs above and watch "
                 "which one moves."), class_name="rp-line"),
        rx.foreach(
            AidState.sim_parts,
            lambda p: rx.box(
                rx.box(
                    rx.el.span(p.label, class_name="sim-part-label"),
                    rx.el.span(p.amount, class_name="sim-part-amount"),
                    class_name="sim-part-head",
                ),
                rx.box(rx.el.i(style={"width": p.weight.to_string() + "%"}),
                       class_name="cp-bar", style={"maxWidth": "none"}),
                rx.box(p.note, class_name="sim-part-note"),
                class_name="sim-part",
            ),
        ),
        class_name="card",
        style={"marginTop": "var(--s4)"},
    )


def _sim_pay() -> rx.Component:
    return rx.box(
        rx.heading("What four kinds of colleges would cost you",
                   size="4", style={"marginTop": "var(--s6)"}),
        rx.box(rx.text(AidState.sim_headline, class_name="rp-line"),
               class_name="card report"),
        rx.foreach(
            AidState.sim_pay,
            lambda e: rx.box(
                rx.box(
                    rx.box(
                        rx.el.span(e.name, class_name="s-name"),
                        rx.cond(e.best,
                                rx.el.span("cheapest for you", class_name="pill pill-good"),
                                rx.fragment()),
                        rx.el.span(e.meets.to_string() + "% of need met",
                                   class_name="pill pill-neutral"),
                        class_name="ct-name",
                    ),
                    rx.box(e.blurb, class_name="lr-sub"),
                    rx.box(rx.el.i(style={"width": e.bar.to_string() + "%"}),
                           class_name="cp-bar", style={"maxWidth": "none"}),
                    style={"flex": "1", "minWidth": "0"},
                ),
                rx.box(
                    rx.box(e.you_pay, class_name="ct-net"),
                    rx.box("you'd pay", class_name="rp-lbl"),
                    class_name="ct-right",
                ),
                rx.box(
                    rx.el.span("sticker ", class_name="faint"),
                    rx.el.span(e.cost),
                    rx.el.span(" · need ", class_name="faint"),
                    rx.el.span(e.need),
                    rx.el.span(" · they cover ", class_name="faint"),
                    rx.el.span(e.met),
                    rx.el.span(" · Pell ", class_name="faint"),
                    rx.el.span(e.pell),
                    class_name="sim-maths",
                ),
                class_name="school sim-pay-row",
            ),
        ),
        style={"marginTop": "var(--s4)"},
    )


def _sim_experiments() -> rx.Component:
    return rx.box(
        rx.heading("Try it", size="4", style={"marginTop": "var(--s6)"}),
        rx.text(("These are common beliefs about aid. Tap one to see what it actually "
                 "does."), class_name="rp-line"),
        rx.foreach(
            AidState.sim_experiments,
            lambda x: rx.box(
                rx.box(
                    rx.el.span(x.label, class_name="sim-exp-label"),
                    rx.el.span(x.delta, class_name="sim-exp-delta",
                               custom_attrs={"data-dir": x.direction}),
                    class_name="sim-exp-head",
                ),
                rx.box(x.teaches, class_name="sim-exp-teaches"),
                rx.el.button("Apply it", type="button", class_name="btn btn-ghost",
                             on_click=AidState.run_experiment(x.key)),
                class_name="card sim-exp",
            ),
        ),
        style={"marginTop": "var(--s4)"},
    )


def _my_colleges() -> rx.Component:
    """The same calculation, run against the list the student actually has.

    Two figures per college rather than one: we have a cited sticker price for
    each, but not its percent-of-need-met, and a single confident number built
    on a guessed generosity is exactly the wrong thing to hand a family
    working out whether they can afford this."""
    return rx.box(
        rx.heading("What your list would cost you", size="4",
                   style={"marginTop": "var(--s6)"}),
        rx.cond(
            AidState.my_colleges_count > 0,
            rx.box(
                rx.box(
                    ("The sticker prices below are the published ones. What you'd actually "
                     "pay depends on how much of your need each college covers. That "
                     "varies a lot and we don't have it for these schools, so you get a "
                     "range instead of one number."),
                    class_name="lr-sub",
                    style={"marginBottom": "var(--s3)"},
                ),
                rx.foreach(
                    AidState.my_colleges,
                    lambda e: rx.cond(
                        e.has_cost,
                        rx.box(
                            rx.box(
                                rx.el.span(e.name, class_name="s-name"),
                                rx.cond(e.best,
                                        rx.el.span("cheapest for you",
                                                   class_name="pill pill-good"),
                                        rx.fragment()),
                                class_name="ct-name",
                            ),
                            rx.box(
                                "Sticker " + e.cost + " · your need " + e.need +
                                " · Pell " + e.pell,
                                class_name="lr-sub",
                            ),
                            rx.box(
                                rx.el.strong("You'd pay roughly " +
                                             e.generous + " – " + e.typical),
                                rx.box("the low end if they meet all of your "
                                       "need, the high end if they meet 60%",
                                       class_name="lr-sub"),
                                style={"marginTop": "var(--s2)"},
                            ),
                            rx.box(
                                rx.el.span("Sticker price source: "),
                                rx.el.a("published " + e.data_year,
                                        href=e.source_url, target="_blank",
                                        rel="noopener noreferrer"),
                                class_name="fit-src",
                            ),
                            class_name="card",
                            style={"marginBottom": "var(--s3)"},
                        ),
                        rx.box(
                            rx.box(e.name, class_name="s-name"),
                            rx.box("We don't have a published cost for this one yet.",
                                   class_name="lr-sub"),
                            class_name="card",
                            style={"marginBottom": "var(--s3)"},
                        ),
                    ),
                ),
                rx.box(AidState.net_price_note, class_name="fit-caveat"),
            ),
            rx.box(
                rx.box(("Add colleges to your list to see what each one would cost with the "
                        "numbers above.")),
                rx.link(btn("Add schools", "secondary", type="button"),
                        href="/applications"),
                class_name="card",
            ),
        ),
    )


def _when() -> rx.Component:
    """Where the student is in the FAFSA year.

    Filing late is the most expensive ordinary mistake in this whole process,
    because several states and many colleges award their own money until it
    runs out. The app had no idea what month it was, so it could never say so
    at the moment it mattered."""
    return rx.box(
        rx.box(
            rx.el.strong(AidState.fafsa_when["headline"]),
            rx.box(AidState.fafsa_when["detail"],
                   style={"marginTop": "var(--s2)"}),
            class_name="card note",
            custom_attrs={"data-urgent": AidState.fafsa_when["urgent"]},
        ),
        style={"marginBottom": "var(--s4)"},
    )


def _simulator() -> rx.Component:
    return rx.box(
        rx.box(
            rx.box("Read this first", class_name="note-tag"),
            rx.text(
                ("These numbers are for learning, not a quote. The Pell amounts and "
                 "poverty guidelines are the official ones for ") + fafsa.AWARD_YEAR + (", but the Student Aid Index formula here is simplified, so treat the "
                                                  "result as a ballpark. For a real number, use the net price "
                                                  "calculator on each college's website (every US college has to have "
                                                  "one) and talk to their financial aid office.")),
            class_name="card note",
        ),
        _sim_inputs(),
        _sim_result(),
        _sim_parts(),
        _sim_pay(),
        _my_colleges(),
        _sim_experiments(),
    )


def _cost(c) -> rx.Component:
    return rx.box(
        rx.box(
            rx.box(
                rx.box(
                    rx.el.span(c.name, class_name="s-name"),
                    rx.cond(c.binding,
                            rx.el.span("binding", class_name="pill pill-warn"),
                            rx.fragment()),
                    rx.cond(c.needs_css,
                            rx.el.span("CSS", class_name="pill pill-neutral"),
                            rx.fragment()),
                    class_name="ct-name",
                ),
                rx.box(
                    rx.el.span(c.round_name),
                    rx.cond(c.aid_deadline != "",
                            rx.el.span(" · aid due ", c.aid_deadline),
                            rx.fragment()),
                    class_name="lr-sub",
                ),
                rx.box(rx.el.i(style={"width": c.bar.to_string() + "%"}),
                       class_name="cp-bar", style={"maxWidth": "none"}),
                style={"flex": "1", "minWidth": "0"},
            ),
            rx.box(
                rx.box(c.net, class_name="ct-net"),
                rx.box("you'd pay", class_name="rp-lbl"),
                class_name="ct-right",
            ),
            rx.el.button(rx.cond(AidState.open_school == c.id, "▴", "▾"),
                         class_name="mini", type="button",
                         on_click=AidState.toggle_school(c.id)),
            class_name="ct-top",
        ),

        rx.cond(
            AidState.open_school == c.id,
            rx.box(
                rx.box(
                    rx.box(
                        rx.el.label("Sticker price"),
                        rx.el.input(class_name="input", placeholder="$70,000",
                                    default_value=c.sticker,
                                    key="k" + c.id.to_string(),
                                    on_blur=lambda v: AidState.set_money(
                                        c.id, "sticker", v)),
                        class_name="field",
                    ),
                    rx.box(
                        rx.el.label("Aid offered"),
                        rx.el.input(class_name="input", placeholder="$38,000",
                                    default_value=c.aid,
                                    key="a" + c.id.to_string(),
                                    on_blur=lambda v: AidState.set_money(
                                        c.id, "aid_offered", v)),
                        class_name="field",
                    ),
                    rx.box(
                        rx.el.label("Net price (from their calculator)"),
                        rx.el.input(class_name="input", placeholder="$32,000",
                                    default_value=c.net,
                                    key="n" + c.id.to_string(),
                                    on_blur=lambda v: AidState.set_money(
                                        c.id, "net_cost", v)),
                        class_name="field",
                    ),
                    rx.box(
                        rx.el.label("Aid deadline"),
                        rx.el.input(type="date", class_name="input",
                                    on_change=lambda v: AidState.set_aid_deadline(c.id, v)),
                        class_name="field",
                    ),
                    class_name="s-fields",
                ),
                rx.box(
                    rx.box(
                        rx.el.label("Round"),
                        rx.el.select(
                            *[rx.el.option(v, value=k) for k, v in ROUND_OPTIONS],
                            class_name="input", value=c.round_name,
                            on_change=lambda v: AidState.set_round(c.id, v),
                        ),
                        class_name="field",
                    ),
                    rx.box(
                        rx.el.label("Needs a CSS Profile"),
                        rx.el.button(
                            rx.cond(c.needs_css, "Yes, it does", "No / not checked"),
                            type="button", class_name="btn btn-secondary",
                            on_click=AidState.toggle_css(c.id)),
                        class_name="field",
                    ),
                    class_name="s-fields",
                ),
                class_name="s-panel",
            ),
            rx.fragment(),
        ),
        class_name="school",
    )


def _flag(f) -> rx.Component:
    return rx.box(
        rx.box(f.title, class_name="note-tag"),
        rx.text(f.detail),
        class_name=rx.cond(f.level == "warn", "card note warn", "card note"),
        style={"marginTop": "var(--s3)"},
    )


def _costs() -> rx.Component:
    return rx.box(
        rx.box(
            rx.text(AidState.cost_line, class_name="rp-line"),
            rx.box(
                rx.box(rx.box(AidState.priced, class_name="rp-num"),
                       rx.box("priced", class_name="rp-lbl"), class_name="rp-stat"),
                rx.box(rx.box(AidState.cheapest_net, class_name="rp-num"),
                       rx.box("cheapest", class_name="rp-lbl"), class_name="rp-stat"),
                rx.box(rx.box(AidState.spread, class_name="rp-num"),
                       rx.box("spread", class_name="rp-lbl"), class_name="rp-stat"),
                class_name="rp-stats",
            ),
            class_name="card report",
        ),
        rx.foreach(AidState.flag_rows, _flag),
        rx.cond(
            AidState.cost_rows.length() > 0,
            rx.box(rx.foreach(AidState.cost_rows, _cost),
                   style={"marginTop": "var(--s4)"}),
            rx.box(rx.text("Add colleges on the applications screen and they "
                           "show up here.", class_name="faint"),
                   class_name="card", style={"marginTop": "var(--s4)"}),
        ),
    )


def _scholarship(s) -> rx.Component:
    return rx.box(
        rx.box(
            rx.box(
                rx.box(
                    rx.cond(s.url != "",
                            rx.el.a(s.name, href=s.url, target="_blank",
                                    rel="noopener noreferrer", class_name="lr-name"),
                            rx.el.span(s.name, class_name="lr-name")),
                    rx.cond(s.urgent,
                            rx.el.span(s.days, "d left", class_name="pill pill-warn"),
                            rx.fragment()),
                    class_name="ct-name",
                ),
                rx.box(
                    rx.el.span(s.amount),
                    rx.cond(s.deadline != "", rx.el.span(" · ", s.deadline),
                            rx.fragment()),
                    class_name="lr-sub",
                ),
                style={"flex": "1", "minWidth": "0"},
            ),
            rx.box(
                rx.el.select(
                    *[rx.el.option(v, value=k) for k, v in SCH_STATUS],
                    class_name="input mini-select", value=s.status,
                    on_change=lambda v: AidState.set_scholarship_status(s.id, v),
                ),
                rx.el.button("×", class_name="mini", type="button",
                             on_click=AidState.remove_scholarship(s.id)),
                class_name="lr-right",
            ),
            class_name="lr-top",
        ),
        class_name=rx.cond(s.status_key == "won", "list-row stack won",
                           "list-row stack"),
    )


def _scholarships() -> rx.Component:
    return rx.box(
        rx.box(
            rx.text(("Local scholarships get far fewer applicants than national ones, so "
                     "your odds are much better for the same work."), class_name="rp-line"),
            rx.box(
                rx.box(rx.box(AidState.won, class_name="rp-num"),
                       rx.box("won", class_name="rp-lbl"), class_name="rp-stat"),
                rx.box(rx.box(AidState.chasing, class_name="rp-num"),
                       rx.box("still chasing", class_name="rp-lbl"),
                       class_name="rp-stat"),
                class_name="rp-stats",
            ),
            class_name="card report",
        ),
        rx.cond(
            AidState.scholarships.length() > 0,
            rx.box(rx.foreach(AidState.scholarships, _scholarship),
                   style={"marginTop": "var(--s4)"}),
            rx.box(rx.text(("Nothing tracked yet. Ask your counselor, your local library, and "
                            "your parents' employers. That's where a lot of the winnable ones "
                            "are."),
                           class_name="faint"),
                   class_name="card", style={"marginTop": "var(--s4)"}),
        ),
        rx.form(
            rx.box(
                rx.box(rx.el.label("Scholarship"),
                       rx.el.input(class_name="input", name="name",
                                   placeholder="Rotary Club of Springfield"),
                       class_name="field"),
                rx.box(rx.el.label("Amount"),
                       rx.el.input(class_name="input", name="amount",
                                   placeholder="$2,500"),
                       class_name="field"),
                rx.box(rx.el.label("Deadline"),
                       rx.el.input(class_name="input", name="deadline", type="date"),
                       class_name="field"),
                rx.box(rx.el.label("Link"),
                       rx.el.input(class_name="input", name="url",
                                   placeholder="https://…"),
                       class_name="field"),
                rx.el.button("Add", class_name="btn btn-primary", type="submit"),
                class_name="add-row",
            ),
            on_submit=AidState.add_scholarship,
            reset_on_submit=True,
        ),
    )


def _learn() -> rx.Component:
    return rx.box(
        rx.box(
            rx.text(("A lot of this is just jargon. Here's what the words mean in plain "
                     "English."),
                    class_name="rp-line"),
            class_name="card report",
        ),
        rx.box(
            rx.foreach(
                AidState.glossary,
                lambda t: rx.box(
                    rx.box(t.word, class_name="gl-word"),
                    rx.box(t.meaning, class_name="gl-mean"),
                    class_name="gl",
                ),
            ),
            class_name="card",
            style={"marginTop": "var(--s4)"},
        ),
    )


def aid_page() -> rx.Component:
    return shell(
        rx.box(
            rx.box(
                rx.link("← Home", href="/home", class_name="btn btn-ghost"),
                rx.heading("Paying for it", size="5"),
                class_name="screen-head",
            ),

            rx.cond(
                AidState.just_earned != "",
                rx.box(
                    rx.box("🏆", class_name="tic"),
                    rx.box(rx.el.strong("Checkpoint reached"),
                           rx.box(AidState.just_earned, class_name="faint")),
                    rx.spacer(),
                    rx.el.button("Nice", class_name="btn btn-ghost", type="button",
                                 on_click=AidState.dismiss_earned),
                    class_name="toast",
                ),
                rx.fragment(),
            ),

            rx.box(
                rx.box("Before anything else", class_name="note-tag"),
                rx.text(AidState.DISCLAIMER),
                class_name="card note",
            ),

            error_box(AidState.error),
            _tabs(),

            _when(),
            rx.cond(AidState.is_checklist, _checklist(), rx.fragment()),
            rx.cond(AidState.is_simulator, _simulator(), rx.fragment()),
            rx.cond(AidState.is_costs, _costs(), rx.fragment()),
            rx.cond(AidState.is_scholarships, _scholarships(), rx.fragment()),
            rx.cond(AidState.is_learn, _learn(), rx.fragment()),
            class_name="screen-wrap",
        ),
    )
