"""
Profile: what the student has told us, and what it adds up to.

The order of this screen is the argument it makes. The numbers come first,
because a student who opens this wants to know where they stand, not to fill
in a form. The form is underneath, framed as the thing that sharpens the
numbers above it.

The loudest element on the page is the mislabel warning: a college the student
has written "safety" beside that its own published data says is a reach. That
is a specific, expensive, extremely common mistake, and it is the one thing
here that genuinely justifies raising a student's pulse.

Every published figure is shown with its source and year attached. Nothing on
this screen is a number the app made up, and there is deliberately no
"chance of admission" anywhere in it — see services/fit.py for why.
"""

from __future__ import annotations

import reflex as rx


from veritagnosis.states.profile_state import (
    CAREER_OPTIONS,
    INTENSITIES,
    MAJOR_OPTIONS,
    ProfileState,
)
from veritagnosis.ui.theme import btn, shell

_WRAP = {"display": "flex", "flexWrap": "wrap", "gap": "var(--s2)"}


def _pick(label: str, selected, handler) -> rx.Component:
    return rx.el.button(
        label, type="button", class_name="tab",
        custom_attrs={"aria-selected": rx.cond(selected == label, "true", "false")},
        on_click=handler(label),
    )


# ---------------------------------------------------------------- readiness
def _dim(d) -> rx.Component:
    """One readiness dimension: label, bar, number, and why."""
    return rx.box(
        rx.box(d["label"], class_name="rd-dim-lab"),
        rx.box(
            rx.el.i(style={"width": d["pct"]}, class_name="rd-fill"),
            class_name="rd-track",
        ),
        rx.box(d["score"], class_name="rd-val"),
        rx.cond(d["why"] != "", rx.box(d["why"], class_name="rd-why"),
                rx.fragment()),
        class_name="rd-dim",
    )


def _readiness() -> rx.Component:
    return rx.box(
        rx.box(
            rx.box(
                rx.box(ProfileState.readiness_overall.to_string(),
                       class_name="rd-score"),
                rx.box("readiness", class_name="rd-score-lab"),
            ),
            class_name="rd-head",
        ),
        rx.box(rx.foreach(ProfileState.readiness_dims, _dim),
               class_name="rd-dims"),
        class_name="card", style={"marginBottom": "var(--s4)"},
    )


# --------------------------------------------------------------- the bands
def _band(f) -> rx.Component:
    """The published middle-50% drawn on a fixed scale, with the student on it."""
    return rx.box(
        rx.box(
            rx.box(class_name="band-rail"),
            rx.box(class_name="band-fill",
                   style={"left": f["band_left"], "width": f["band_width"]}),
            rx.box(class_name="band-mark", style={"left": f["marker"]},
                   custom_attrs={"data-p": f["place"]}),
            class_name="band",
        ),
        rx.box(
            rx.box(rx.cond(f["metric"] == "ACT", "1", "400")),
            rx.box("admitted middle 50%: " + f["low"] + "–" + f["high"]),
            rx.box(rx.cond(f["metric"] == "ACT", "36", "1600")),
            class_name="band-ends",
        ),
        rx.box(f["sentence"], class_name="fit-sentence"),
    )


def _fix_button(f, key: str) -> rx.Component:
    return rx.cond(
        f[key] != "",
        rx.el.button(f[key], type="button", class_name="sug",
                     on_click=ProfileState.rename_school(f["school_id"], f[key])),
        rx.fragment(),
    )


def _unmatched(f) -> rx.Component:
    """A name on the list that is not a college the catalogue knows.

    Says plainly what to do: pick the full name, or re-add it with one. One
    tap renames the row, and the card fills with that college's data."""
    return rx.cond(
        f["sug1"] != "",
        rx.box(
            rx.box("“" + f["name"] + "” isn't a full college name. "
                   "Which one do you mean?", class_name="unmatched-q"),
            rx.box(_fix_button(f, "sug1"), _fix_button(f, "sug2"),
                   _fix_button(f, "sug3"), class_name="sug-list"),
        ),
        rx.box(
            "“" + f["name"] + "” isn't a college we can find. Remove it on "
            "My colleges and add it again with its full name, like "
            "“University of Michigan-Ann Arbor”.",
            class_name="unmatched-q",
        ),
    )


def _fit_card(f) -> rx.Component:
    return rx.box(
        rx.box(
            rx.box(f["name"], class_name="fit-name"),
            rx.cond(
                f["data_tier"] != "",
                rx.box(f["data_tier"], class_name="fit-tier",
                       custom_attrs={"data-t": f["data_tier"]}),
                rx.fragment(),
            ),
            rx.cond(
                f["accept_rate"] != "",
                rx.box("admits " + f["accept_rate"], class_name="fit-rate"),
                rx.fragment(),
            ),
            class_name="fit-top",
        ),
        rx.cond(
            f["has_data"] == "no",
            _unmatched(f),
            rx.box(
                rx.cond(f["metric"] != "", _band(f),
                        rx.box("No test-score comparison for this college.",
                               class_name="faint")),
                rx.cond(
                    f["cost"] != "",
                    rx.box("Sticker cost " + f["cost"] + " a year, before aid.",
                           class_name="faint"),
                    rx.fragment(),
                ),
                rx.box(
                    rx.el.span("Source: "),
                    rx.el.a("published data " + f["data_year"],
                            href=f["source_url"], target="_blank",
                            rel="noopener noreferrer"),
                    class_name="fit-src",
                ),
                rx.cond(
                    f["caveat"] != "",
                    rx.box(f["caveat"], class_name="fit-caveat"),
                    rx.fragment(),
                ),
            ),
        ),
        class_name="fit-card",
        custom_attrs={"data-flag": f["disagrees"]},
    )


def _mismatch(f) -> rx.Component:
    return rx.box(
        rx.box("You have " + f["name"] + " down as a " + f["student_tier"] + ".",
               class_name="mismatch-h"),
        rx.box(
            "Its published data makes it a " + f["data_tier"] + ". " +
            f["sentence"],
        ),
        class_name="mismatch",
    )


def _where_you_stand() -> rx.Component:
    return rx.box(
        rx.heading("Where you actually stand", size="4",
                   style={"marginBottom": "var(--s3)"}),

        rx.foreach(ProfileState.disagreements, _mismatch),

        rx.cond(
            ProfileState.school_count > 0,
            rx.box(rx.foreach(ProfileState.fits, _fit_card)),
            rx.box(
                rx.box("No colleges on your list yet."),
                rx.link(btn("Add some schools", "secondary", type="button"),
                        href="/applications"),
                style={"padding": "var(--s4) 0"},
            ),
        ),

        rx.foreach(
            ProfileState.fit_warnings,
            lambda w: rx.box(w, class_name="fit-caveat",
                             style={"marginTop": "var(--s3)"}),
        ),
                class_name="card", style={"marginBottom": "var(--s4)"},
    )


# ------------------------------------------------------- gaps and next steps
def _spot(b) -> rx.Component:
    return rx.box(
        rx.box(b["icon"], class_name="spot-i"),
        rx.box(
            rx.box(b["title"], class_name="spot-t"),
            rx.box(b["body"], class_name="spot-b"),
            rx.cond(b["action"] != "",
                    rx.box(b["action"], class_name="spot-b"), rx.fragment()),
        ),
        class_name="spot",
    )


def _gaps() -> rx.Component:
    return rx.cond(
        ProfileState.blind_spots.length() > 0,
        rx.box(
            rx.heading("What you have not looked at yet", size="4",
                       style={"marginBottom": "var(--s3)"}),
            rx.foreach(ProfileState.blind_spots, _spot),
            class_name="card", style={"marginBottom": "var(--s4)"},
        ),
        rx.fragment(),
    )


def _steps() -> rx.Component:
    return rx.cond(
        ProfileState.next_steps.length() > 0,
        rx.box(
            rx.heading("Do these next", size="4",
                       style={"marginBottom": "var(--s3)"}),
            rx.foreach(
                ProfileState.next_steps,
                lambda s, i: rx.box(
                    rx.box((i + 1).to_string() + ".", class_name="step-n"),
                    rx.box(s),
                    class_name="step-row",
                ),
            ),
            class_name="card", style={"marginBottom": "var(--s4)"},
        ),
        rx.fragment(),
    )


def _num_field(label: str, hint: str, value, problem, handler,
               placeholder: str) -> rx.Component:
    """One number the student types about themselves.

    The problem line appears while they type rather than after they save,
    because a GPA of 45 silently dropped by the parser is indistinguishable
    from one that was never entered.
    """
    return rx.box(
        rx.el.label(label),
        rx.el.input(
            class_name="input", placeholder=placeholder,
            value=value, on_change=handler,
            input_mode="decimal", auto_complete="off",
        ),
        rx.cond(
            problem != "",
            rx.box(problem, class_name="num-problem"),
            rx.box(hint, class_name="num-hint"),
        ),
        class_name="field num-field",
    )


def _your_numbers() -> rx.Component:
    """GPA and test scores.

    These drive the fit bands and the readiness score, and have done since
    that engine was written — student_stats() reads user.gpa and the TestScore
    rows, and every comparison on this screen uses them. There was just nowhere
    to type them, so the app told every student, permanently, that they had not
    entered a score. This is that missing form.
    """
    return rx.box(
        rx.box(
            rx.heading("Your numbers", size="4"),
            class_name="num-head",
        ),
        rx.box(
            _num_field("GPA", "Unweighted, out of 4 — or weighted if that is "
                              "what your school reports.",
                       ProfileState.gpa_input, ProfileState.gpa_problem,
                       ProfileState.set_gpa_input, "3.8"),
            _num_field("SAT", "Total score, 400–1600.",
                       ProfileState.sat_input, ProfileState.sat_problem,
                       ProfileState.set_sat_input, "1380"),
            _num_field("ACT", "Composite, 1–36.",
                       ProfileState.act_input, ProfileState.act_problem,
                       ProfileState.set_act_input, "31"),
            class_name="num-grid",
        ),
        rx.box(
            rx.el.button("Save my numbers", type="button",
                         class_name="btn btn-primary",
                         disabled=~ProfileState.scores_ok,
                         on_click=ProfileState.save_scores),
            rx.cond(
                ProfileState.scores_msg != "",
                rx.box(ProfileState.scores_msg, class_name="num-saved"),
                rx.fragment(),
            ),
            class_name="num-actions",
        ),
        class_name="card your-numbers",
    )


# ------------------------------------------------------------- the form
def _ec_row(ec, index) -> rx.Component:
    is_lead = ec["leadership"] == "yes"
    return rx.box(
        rx.box(
            rx.el.strong(ec["name"]),
            rx.box(ec["intensity"] + " · " + ec["years"] + " yr",
                   class_name="faint"),
            style={"flex": "1", "minWidth": "0"},
        ),
        rx.el.button(
            rx.cond(is_lead, "★ Leadership", "☆ Leadership"),
            type="button", class_name="tab",
            custom_attrs={"aria-selected": rx.cond(is_lead, "true", "false")},
            on_click=ProfileState.toggle_leadership(index),
        ),
        rx.el.button("Remove", type="button", class_name="btn btn-ghost",
                     on_click=ProfileState.remove_extracurricular(index)),
        style={"display": "flex", "alignItems": "center", "gap": "var(--s3)",
               "padding": "var(--s3) var(--s4)",
               "border": "1px solid var(--border)",
               "borderRadius": "var(--r-md)", "background": "var(--surface)"},
    )


def _details() -> rx.Component:
    return rx.box(
        rx.heading("Your details", size="4", style={"marginBottom": "var(--s4)"}),

        rx.box(
            rx.el.label("What field interests you?"),
            rx.box(*[_pick(o, ProfileState.career_interest,
                           ProfileState.set_career_interest)
                     for o in CAREER_OPTIONS], style=_WRAP),
            style={"marginBottom": "var(--s4)"},
        ),
        rx.box(
            rx.el.label("Thinking about a major?"),
            rx.box(*[_pick(o, ProfileState.major_preference,
                           ProfileState.set_major_preference)
                     for o in MAJOR_OPTIONS], style=_WRAP),
            style={"marginBottom": "var(--s4)"},
        ),

        rx.box(
            rx.el.label("What do you spend time on?"),
            rx.box(rx.foreach(ProfileState.extracurriculars, _ec_row),
                   style={"display": "flex", "flexDirection": "column",
                          "gap": "var(--s2)", "margin": "var(--s2) 0"}),
            rx.box(
                rx.box(
                    rx.el.input(class_name="input", placeholder="Robotics club",
                                default_value=ProfileState.new_ec_name,
                                key="ecn-" + ProfileState.form_epoch.to_string(),
                                on_change=ProfileState.set_new_ec_name),
                    class_name="field", style={"flex": "2", "minWidth": "160px"},
                ),
                rx.box(
                    rx.el.input(class_name="input", type="number", min="1",
                                max="6", default_value=ProfileState.new_ec_years,
                                on_change=ProfileState.set_new_ec_years),
                    class_name="field", style={"flex": "1", "minWidth": "80px"},
                ),
                style={"display": "flex", "gap": "var(--s3)",
                       "flexWrap": "wrap"},
            ),
            rx.box(*[_pick(i, ProfileState.new_ec_intensity,
                           ProfileState.set_new_ec_intensity)
                     for i in INTENSITIES],
                   style={**_WRAP, "margin": "var(--s2) 0"}),
            btn("Add activity", "secondary", type="button",
                on_click=ProfileState.add_extracurricular),
            style={"marginBottom": "var(--s4)"},
        ),

        rx.box(
            rx.box(
                rx.el.label("Earliest deadline you are working towards"),
                rx.el.input(class_name="input", type="date",
                            default_value=ProfileState.app_deadline,
                            key="dl-" + ProfileState.form_epoch.to_string(),
                            on_change=ProfileState.set_app_deadline),
                class_name="field",
            ),
            rx.box(
                rx.el.label("How many schools are you aiming for?"),
                rx.el.input(class_name="input", type="number", min="1", max="20",
                            default_value=ProfileState.target_schools_count.to_string(),
                            on_change=ProfileState.set_target_schools_count),
                class_name="field",
            ),
            style={"display": "flex", "gap": "var(--s3)", "flexWrap": "wrap",
                   "marginBottom": "var(--s4)"},
        ),

        rx.box(
            rx.el.label("How are you playing this?"),
            rx.box(
                _pick("reach", ProfileState.priority, ProfileState.set_priority),
                _pick("balanced", ProfileState.priority, ProfileState.set_priority),
                _pick("safety", ProfileState.priority, ProfileState.set_priority),
                style={**_WRAP, "marginTop": "var(--s2)"},
            ),
            style={"marginBottom": "var(--s4)"},
        ),

        rx.box(
            btn("Save profile", type="button",
                on_click=ProfileState.save_profile),
            rx.cond(ProfileState.saved_msg != "",
                    rx.box(ProfileState.saved_msg, class_name="faint"),
                    rx.fragment()),
            style={"display": "flex", "alignItems": "center",
                   "gap": "var(--s3)"},
        ),
        class_name="card",
    )


def profile_page() -> rx.Component:
    return shell(
        rx.box(
            rx.box(
                rx.link("← Home", href="/home", class_name="btn btn-ghost"),
                class_name="screen-head",
            ),
            rx.heading("My profile", size="5", style={"marginBottom": "var(--s5)"}),
            rx.cond(
                ProfileState.load_error != "",
                rx.box(ProfileState.load_error, class_name="fit-caveat",
                       style={"marginBottom": "var(--s4)"}),
                rx.fragment(),
            ),
            # Before the readiness panel on purpose: every number in it is
            # computed from this form, so a student who has not filled it in
            # should meet the inputs first rather than a score of zero.
            _your_numbers(),
            _readiness(),
            _where_you_stand(),
            _gaps(),
            _steps(),
            _details(),
            class_name="screen-wrap",
        ),
    )
