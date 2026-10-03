"""
The application work: the school list, the essay coach, and
recommenders.

Merged from: applications, essays, recommendations.
"""
from __future__ import annotations

import reflex as rx
from veritagnosis.states.apply_state import SchoolsState
from veritagnosis.ui.theme import error_box, shell
from veritagnosis.states.auth_state import AuthState
from veritagnosis.states.apply_state import EssayState
from veritagnosis.ui.widgets import coach_figure
from veritagnosis.ui.theme import shell
from veritagnosis.states.apply_state import RecsState
from veritagnosis.services import prose


# ====================================================================
# applications
# ====================================================================

def _ring(pct, dash) -> rx.Component:
    """The progress ring. An SVG arc rather than a bar because a school is a
    single thing making its way to done, and a circle reads that way."""
    return rx.el.svg(
        rx.el.svg.circle(cx="30", cy="30", r="26", fill="none",
                         stroke="var(--surface-3)", stroke_width="6"),
        rx.el.svg.circle(
            cx="30", cy="30", r="26", fill="none", stroke="var(--accent)",
            stroke_width="6", stroke_linecap="round",
            transform="rotate(-90 30 30)",
            stroke_dasharray="163.36",
            stroke_dashoffset=dash,
            class_name="ring-live",
        ),
        rx.el.svg.text(pct, x="30", y="35", text_anchor="middle",
                       class_name="ring-num"),
        view_box="0 0 60 60", class_name="ring60",
    )


def _step(st) -> rx.Component:
    """One line of a school's checklist."""
    return rx.box(
        rx.box(rx.cond(st.done, "✓", "○"), class_name="st-mark"),
        rx.box(
            rx.box(
                rx.el.span(st.label, class_name="st-label"),
                rx.cond(st.detail != "",
                        rx.el.span(st.detail, class_name="st-detail"),
                        rx.fragment()),
                class_name="st-head",
            ),
            rx.cond(
                ~st.done & (st.hint != ""),
                rx.box(
                    rx.el.span(st.hint, class_name="st-hint"),
                    rx.link("Go →", href=st.route, class_name="st-go"),
                    class_name="st-body",
                ),
                rx.fragment(),
            ),
            class_name="st-main",
        ),
        class_name=rx.cond(st.done, "st done", "st"),
    )


def _school(s) -> rx.Component:
    return rx.box(
        # the always-visible row
        rx.box(
            _ring(s.progress, s.ring_dash),
            rx.box(
                rx.box(s.name, class_name="s-name"),
                rx.box(
                    rx.el.span(s.status, class_name="s-status"),
                    rx.el.span("·"),
                    rx.el.span(s.when, class_name="s-when"),
                    rx.el.span(" · ", s.letters),
                    rx.cond(
                        s.binding,
                        rx.el.span("binding", class_name="pill pill-warn"),
                        rx.fragment(),
                    ),
                    class_name="lr-sub",
                ),
                rx.cond(
                    s.next_label != "Everything done",
                    rx.box("Next: ", rx.el.strong(s.next_label), class_name="s-next"),
                    rx.box("Everything on this one is done.", class_name="s-next ok"),
                ),
                style={"flex": "1", "minWidth": "0"},
            ),
            rx.el.button(rx.cond(SchoolsState.open_id == s.id, "▴", "▾"),
                         class_name="mini", type="button",
                         title="Show the checklist",
                         on_click=SchoolsState.toggle_open(s.id)),
            class_name="s-top",
            custom_attrs={"data-urgency": s.urgency},
        ),

        # the panel
        rx.cond(
            SchoolsState.open_id == s.id,
            rx.box(
                rx.box(rx.foreach(s.steps, _step), class_name="st-list"),

                rx.box(
                    rx.box(
                        rx.el.label("Deadline"),
                        rx.el.input(
                            type="date", class_name="input",
                            default_value=s.deadline_iso,
                            key=s.deadline_iso,
                            on_change=lambda v: SchoolsState.set_deadline(s.id, v),
                        ),
                        class_name="field",
                    ),
                    rx.box(
                        rx.el.label("Where it's at"),
                        rx.el.select(
                            rx.el.option("Not started", value="not_started"),
                            rx.el.option("In progress", value="in_progress"),
                            rx.el.option("Submitted", value="submitted"),
                            rx.el.option("Accepted", value="accepted"),
                            rx.el.option("Waitlisted", value="waitlisted"),
                            rx.el.option("Rejected", value="rejected"),
                            class_name="input",
                            value=s.status_key,
                            on_change=lambda v: SchoolsState.set_status(s.id, v),
                        ),
                        class_name="field",
                    ),
                    rx.box(
                        rx.el.label("Column"),
                        rx.el.select(
                            rx.el.option("Safety", value="safety"),
                            rx.el.option("Primary", value="target"),
                            rx.el.option("Reach", value="reach"),
                            class_name="input",
                            value=s.tier,
                            on_change=lambda v: SchoolsState.set_tier(s.id, v),
                        ),
                        class_name="field",
                    ),
                    rx.box(
                        rx.el.label("Round"),
                        rx.el.span(s.round_name, class_name="input ro"),
                        rx.el.span("Set the round on the Paying for it screen — "
                                   "it changes when you can compare aid.",
                                   class_name="faint tiny"),
                        class_name="field",
                    ),
                    rx.box(
                        rx.el.label("Letters needed"),
                        rx.el.input(
                            type="number", min="0", max="10", class_name="input",
                            default_value=s.recs_required.to_string(),
                            key="r" + s.recs_required.to_string(),
                            on_change=lambda v: SchoolsState.set_requirement(
                                s.id, "recs", v),
                        ),
                        class_name="field",
                    ),
                    class_name="s-fields",
                ),

                rx.box(
                    rx.el.label("Why this college"),
                    rx.el.textarea(
                        class_name="input s-notes",
                        placeholder="What actually draws you here? Two or three "
                                    "specifics beat a paragraph of adjectives — "
                                    "and you will need these words later.",
                        default_value=s.notes,
                        key="n" + s.id.to_string(),
                        on_blur=lambda v: SchoolsState.set_notes(s.id, v),
                        rows="4",
                    ),
                    class_name="field",
                ),

                rx.box(
                    rx.el.button("Remove this college", class_name="btn btn-ghost",
                                 type="button", on_click=SchoolsState.remove(s.id)),
                    style={"marginTop": "var(--s3)", "textAlign": "right"},
                ),
                class_name="s-panel",
            ),
            rx.fragment(),
        ),
        class_name="school",
        custom_attrs={"data-urgency": s.urgency},
    )


def _column(title: str, rows) -> rx.Component:
    return rx.box(
        rx.box(title, class_name="col-head"),
        rx.cond(
            rows.length() > 0,
            rx.foreach(rows, _school),
            rx.box(rx.text("Nothing here yet.", class_name="faint"),
                   class_name="school"),
        ),
    )


def _summary() -> rx.Component:
    return rx.box(
        rx.box(
            _ring(SchoolsState.average, SchoolsState.average_dash),
            rx.box(
                rx.text(SchoolsState.next_line, class_name="rp-line"),
                rx.box(
                    rx.box(rx.box(SchoolsState.total, class_name="rp-num"),
                           rx.box("colleges", class_name="rp-lbl"),
                           class_name="rp-stat"),
                    rx.box(rx.box(SchoolsState.average, class_name="rp-num"),
                           rx.box("avg done", class_name="rp-lbl"),
                           class_name="rp-stat"),
                    rx.box(rx.box(SchoolsState.submitted, class_name="rp-num"),
                           rx.box("submitted", class_name="rp-lbl"),
                           class_name="rp-stat"),
                    rx.box(rx.box(SchoolsState.urgent, class_name="rp-num"),
                           rx.box("due soon", class_name="rp-lbl"),
                           class_name="rp-stat"),
                    class_name="rp-stats",
                ),
                class_name="rp-right",
            ),
            class_name="rp-top",
        ),
        rx.box(
            rx.el.span("Sort by", class_name="faint"),
            *[
                rx.el.button(
                    label, type="button", class_name="cat-chip",
                    custom_attrs={"aria-pressed": SchoolsState.sort_by == key},
                    on_click=SchoolsState.set_sort(key),
                )
                for key, label in [("deadline", "Deadline"),
                                   ("progress", "Progress"), ("name", "Name")]
            ],
            class_name="cats",
        ),
        class_name="card report",
    )


def applications_page() -> rx.Component:
    return shell(
        rx.box(
            rx.box(
                rx.link("← Home", href="/home", class_name="btn btn-ghost"),
                rx.heading("Application progress", size="5"),
                class_name="screen-head",
            ),
            error_box(SchoolsState.error),

            rx.cond(
                SchoolsState.just_earned != "",
                rx.box(
                    rx.box("🏆", class_name="tic"),
                    rx.box(rx.el.strong("Checkpoint reached"),
                           rx.box(SchoolsState.just_earned, class_name="faint")),
                    rx.spacer(),
                    rx.el.button("Nice", class_name="btn btn-ghost", type="button",
                                 on_click=SchoolsState.dismiss_earned),
                    class_name="toast",
                ),
                rx.fragment(),
            ),

            rx.cond(SchoolsState.has_schools, _summary(), rx.fragment()),

            rx.box(
                # left column: Safety above Reach, as drawn
                rx.box(
                    _column("Safety", SchoolsState.safety),
                    _column("Reach", SchoolsState.reach),
                    class_name="col",
                    style={"gap": "var(--s5)"},
                ),
                # right column: Primary
                rx.box(
                    _column("Primary", SchoolsState.target),
                    class_name="col",
                ),
                class_name="board",
            ),

            rx.form(
                rx.box(
                    rx.box(
                        rx.el.label("School"),
                        rx.el.input(class_name="input", name="name",
                                    placeholder="Type a college name"),
                        class_name="field",
                    ),
                    rx.box(
                        rx.el.label("Column"),
                        rx.el.select(
                            rx.el.option("Safety", value="safety"),
                            rx.el.option("Primary", value="target"),
                            rx.el.option("Reach", value="reach"),
                            class_name="input", name="tier",
                        ),
                        class_name="field",
                    ),
                    rx.el.button("Add", class_name="btn btn-primary", type="submit"),
                    class_name="add-row",
                ),
                on_submit=SchoolsState.add_school,
                reset_on_submit=True,
            ),
            class_name="screen-wrap",
        ),
    )


# ====================================================================
# essays
# ====================================================================

REACTIONS = [("💡", "idea", "I had an idea"),
             ("❤️", "love", "I like this bit"),
             ("🔥", "fire", "I'm on a roll"),
             ("😐", "stuck", "I'm stuck")]

SPRINTS = [5, 10, 20]


def _cat_chip(c) -> rx.Component:
    return rx.el.button(
        rx.box(c.name, class_name="chip-name"),
        rx.box(c.count, class_name="chip-n"),
        type="button", class_name="cat-chip",
        custom_attrs={"data-sev": c.severity,
                      "aria-pressed": EssayState.focus == c.key},
        on_click=EssayState.set_focus(c.key),
    )


def _issue(i) -> rx.Component:
    return rx.box(
        rx.box(
            rx.box(class_name="iss-dot"),
            rx.box(
                rx.box(
                    rx.el.span(i.label, class_name="iss-label"),
                    rx.el.span(i.original, class_name="iss-orig"),
                    class_name="iss-head",
                ),
                rx.cond(
                    EssayState.open_issue == i.idx,
                    rx.box(
                        rx.text(i.why, class_name="iss-why"),
                        rx.cond(
                            i.has_fix & (i.fix != ""),
                            rx.box(
                                rx.el.span(i.original, class_name="was"),
                                rx.el.span("→", class_name="arrow"),
                                rx.el.span(i.fix, class_name="now"),
                                class_name="iss-diff",
                            ),
                            rx.fragment(),
                        ),
                        class_name="iss-body",
                    ),
                    rx.fragment(),
                ),
                class_name="iss-main",
            ),
            class_name="iss-click",
            on_click=EssayState.toggle_issue(i.idx),
        ),
        rx.box(
            rx.cond(
                i.has_fix,
                rx.el.button(i.action, type="button", class_name="btn btn-fix",
                             on_click=EssayState.apply_fix(i.idx)),
                rx.fragment(),
            ),
            rx.el.button("✕", type="button", class_name="btn btn-dismiss",
                         title="Not a problem", on_click=EssayState.dismiss(i.idx)),
            class_name="iss-acts",
        ),
        class_name="iss",
        custom_attrs={"data-sev": i.severity, "data-kind": i.kind},
    )


def _chunk(c) -> rx.Component:
    return rx.cond(
        c.marked,
        rx.el.mark(c.text, class_name="mk",
                   custom_attrs={"data-kind": c.kind},
                   on_click=EssayState.toggle_issue(c.idx)),
        rx.el.span(c.text),
    )


def _para(p) -> rx.Component:
    """One paragraph in the outline. The bar is the share of the essay it takes
    up, which is the thing you cannot see from inside the writing."""
    return rx.box(
        rx.box("¶", p.n, class_name="pa-n"),
        rx.box(
            rx.box(p.opening, class_name="pa-open"),
            rx.box(rx.el.i(style={"width": p.percent.to_string() + "%"}),
                   class_name="cp-bar", style={"maxWidth": "none"}),
            class_name="pa-main",
        ),
        rx.box(p.words, "w", class_name="pa-w"),
        class_name="pa", custom_attrs={"data-tone": p.tone},
    )


def _version(v) -> rx.Component:
    return rx.box(
        rx.box(
            rx.box(v.when, class_name="vr-when"),
            rx.box(v.label, class_name="vr-label"),
            rx.box(v.delta, class_name="vr-delta"),
            class_name="vr-main",
        ),
        rx.el.button("Restore", type="button", class_name="btn btn-fix",
                     on_click=EssayState.restore(v.id)),
        class_name="vr",
    )


def _prompt_row(p) -> rx.Component:
    """One prompt, readable.

    The whole prompt, the word limit, and the one line of advice about what
    that prompt tends to do to a draft. A student choosing between eleven of
    these is making a real decision and needs the actual words to make it.
    """
    return rx.el.button(
        rx.box(
            rx.el.span(p.words, " words", class_name="pr-words"),
            rx.cond(p.picked,
                    rx.el.span("Current", class_name="pr-current"),
                    rx.fragment()),
            class_name="pr-tags",
        ),
        rx.box(p.text, class_name="pr-text"),
        rx.box(p.note, class_name="pr-note"),
        type="button", class_name="pr",
        custom_attrs={"aria-pressed": p.picked},
        on_click=EssayState.pick_prompt(p.key),
    )


def _prompt_picker() -> rx.Component:
    """The chooser, as a modal.

    It used to be an inline list that unrolled underneath everything else:
    click "change prompt" and eleven truncated rows appeared below the fold,
    pushing the page down, with no indication that was what the click did. On a
    narrow screen the coach panel is stacked under the editor, so they appeared
    at the very bottom — which is how this was reported, and fairly.

    A modal is the right shape because choosing a prompt is modal in the real
    sense: it is one decision, it is the only thing you are doing while you do
    it, and it ends. The backdrop is a sibling rather than a parent so that
    clicking the dialog cannot bubble up and dismiss it.
    """
    return rx.cond(
        EssayState.show_prompts,
        rx.fragment(
            rx.box(class_name="pp-backdrop",
                   on_click=EssayState.close_prompts),
            rx.box(
                rx.box(
                    rx.box(
                        rx.heading("Choose your prompt", size="4"),
                        rx.text("You can change this later — it does not delete "
                                "your draft.", class_name="faint tiny"),
                        class_name="pp-head-text",
                    ),
                    rx.spacer(),
                    rx.el.button("✕", type="button", class_name="pp-close",
                                 id="vg-prompt-close",
                                 custom_attrs={"aria-label": "Close"},
                                 on_click=EssayState.close_prompts),
                    class_name="pp-head",
                ),
                rx.box(
                    rx.foreach(EssayState.prompt_list, _prompt_row),
                    class_name="pp-body",
                ),
                class_name="pp-modal", id="vg-prompt-modal",
                custom_attrs={"role": "dialog", "aria-modal": "true"},
            ),
        ),
        rx.fragment(),
    )


def _toolbar() -> rx.Component:
    """The things that make a long session bearable. All of these run in the
    browser — none of them is worth a round trip to the server."""
    return rx.box(
        rx.el.button(rx.el.span("🔊 Read aloud", class_name="lbl"),
                     type="button", id="vg-read", class_name="btn btn-ghost",
                     title="Hear it back. Ctrl+Enter."),
        rx.el.button(rx.el.span("◱ Focus", class_name="lbl"),
                     type="button", id="vg-focus", class_name="btn btn-ghost",
                     title="Hide everything but the words. Escape to leave."),
        # "Save version" and "Versions" used to live here. They are about the
        # history of the draft, not about writing it, and the Draft Journey
        # section below already has both — so this toolbar went from seven
        # controls to four. Fifteen buttons around a text box is the reason a
        # student does not start typing.
        rx.spacer(),
        rx.el.span("Sprint", class_name="faint tiny"),
        *[
            rx.el.button(f"{m}m", type="button", class_name="mini",
                         custom_attrs={"data-sprint": str(m)},
                         title=f"{m} minutes. Write, don't edit.")
            for m in SPRINTS
        ],
        class_name="tools",
    )


def _sprint_bar() -> rx.Component:
    """Driven entirely by essay.js — the server never sees the countdown."""
    return rx.el.div(
        rx.el.span("⏱", class_name="sp-ic"),
        rx.el.span("0:00", id="vg-sprint-time", class_name="sp-time"),
        rx.el.span("0 words", id="vg-sprint-words", class_name="sp-words"),
        rx.el.span("Write. Don't edit. Don't delete.", class_name="sp-rule"),
        rx.el.button("Stop", type="button", id="vg-sprint-stop",
                     class_name="btn btn-ghost"),
        id="vg-sprint", class_name="sprint", hidden=True,
    )


def _editor() -> rx.Component:
    """The wireframe's writing panel: reactions down the left, ruled paper on
    the right — or the same words marked up, or the outline."""
    return rx.box(
        rx.box(
            # Four unexplained emoji down the side of a text box look like
            # decoration, so nobody touched them. The label says what they are.
            rx.el.span("How's it going?", class_name="rx-label"),
            *[
                rx.el.button(
                    emoji, type="button", title=label,
                    custom_attrs={"aria-pressed": EssayState.reaction == key,
                                  "aria-label": label},
                    on_click=EssayState.react(key),
                )
                for emoji, key, label in REACTIONS
            ],
            class_name="reactions",
        ),
        rx.cond(
            EssayState.review_mode,
            rx.box(
                rx.cond(
                    EssayState.chunks.length() > 0,
                    rx.box(rx.foreach(EssayState.chunks, _chunk), class_name="rv-text"),
                    rx.box("Nothing written yet.", class_name="faint"),
                ),
                class_name="editor review",
            ),
            rx.cond(
                EssayState.outline_mode,
                rx.box(
                    rx.cond(
                        EssayState.paras.length() > 0,
                        rx.box(rx.foreach(EssayState.paras, _para), class_name="pa-list"),
                        rx.box("Write a paragraph and its shape shows up here.",
                               class_name="faint"),
                    ),
                    class_name="editor review",
                ),
                # UNCONTROLLED on purpose — this is the cursor fix.
                #
                # `default_value` instead of `value` means React sets the text
                # once when the box appears and then leaves it alone. The
                # browser owns the caret from that point on, so clicking into
                # the middle of a sentence to fix a typo behaves the way it
                # does in every other text box in the world.
                #
                # `key` is how the app takes control back when it needs to. It
                # only changes when the draft is deliberately replaced —
                # loaded, fixed, polished, undone, restored — and a changed key
                # rebuilds the box with the new text. Typing never changes it,
                # so typing never moves the caret.
                rx.el.textarea(
                    default_value=EssayState.body,
                    key=EssayState.doc_version.to_string(),
                    on_change=EssayState.set_body,
                    on_blur=EssayState.save,
                    placeholder="Start anywhere. You can fix it later.",
                    class_name="editor",
                    id="vg-editor",
                    spell_check=True,
                ),
            ),
        ),
        class_name="editor-wrap",
    )


# ====================================================================
# the essay lab
# ====================================================================
#
# The old screen was a report with a text box in the middle of it: score,
# statistics, buttons, the writing, then four more cards of findings below the
# fold. Everything was equally loud and the thing you were supposed to be doing
# — writing — had the least room on the page.
#
# This is a workspace. The draft gets the left column and keeps it. Everything
# the engine has to say lives in one panel on the right, behind tabs, so it is
# available without being in the way. And the panel leads with the single next
# thing to do rather than with a list of twenty.


def _dial() -> rx.Component:
    """The score. A conic gradient driven by one custom property, so the number
    sweeps from the old score to the new one when a fix lands.

    Shown only when there is enough draft to score. Below that floor the same
    ring fills with progress toward the floor instead, which is honest about
    what it is measuring — words written, not quality."""
    return rx.cond(
        EssayState.score_ready,
        rx.box(
            rx.box(
                rx.box(EssayState.score, custom_attrs={"data-pulse": "1"},
                       class_name="dial-num"),
                rx.box("/100", class_name="dial-of"),
                class_name="dial-inner",
            ),
            class_name="dial",
            style={"--p": EssayState.score.to_string()},
            custom_attrs={"data-band": EssayState.band},
        ),
        rx.box(
            rx.box(
                rx.box("—", class_name="dial-num"),
                rx.box("not yet", class_name="dial-of"),
                class_name="dial-inner",
            ),
            class_name="dial dial-gate",
            style={"--p": EssayState.gate_percent.to_string()},
            custom_attrs={"data-band": "unscored"},
        ),
    )


def _stat(value, label: str) -> rx.Component:
    return rx.box(
        rx.box(value, class_name="rp-num"),
        rx.box(label, class_name="rp-lbl"),
        class_name="rp-stat",
    )


def _dim(d) -> rx.Component:
    """One of the five things the score is made of, with its weight on show.

    A single number tells a student nothing they can act on. Five numbers with
    names tell them which part of the draft is the problem, and the weight tells
    them whether it is worth their evening."""
    return rx.box(
        rx.box(
            rx.el.span(d.name, class_name="dim-name"),
            rx.el.span(d.weight, class_name="dim-weight"),
            rx.spacer(),
            rx.el.span(d.value, class_name="dim-val"),
            class_name="dim-head",
        ),
        rx.box(rx.el.i(style={"width": d.value.to_string() + "%"}),
               class_name="cp-bar", style={"maxWidth": "none"}),
        rx.box(d.note, class_name="dim-note"),
        class_name="dim", custom_attrs={"data-tone": d.tone},
    )


def _story_step(s) -> rx.Component:
    """One move of the five-move shape."""
    return rx.box(
        rx.box(
            rx.cond(s.present, rx.el.span("●", class_name="sm-dot"),
                    rx.el.span("○", class_name="sm-dot")),
            class_name="sm-mark",
        ),
        rx.box(
            rx.box(
                rx.el.span(s.name, class_name="sm-name"),
                rx.cond(s.para != "",
                        rx.el.span(s.para, class_name="sm-where"),
                        rx.fragment()),
                rx.spacer(),
                rx.el.span(
                    rx.cond(s.state == "there", "in the draft",
                            rx.cond(s.state == "thin", "thin", "missing")),
                    class_name="sm-state"),
                class_name="sm-head",
            ),
            rx.box(rx.el.i(style={"width": s.strength.to_string() + "%"}),
                   class_name="cp-bar sm-bar", style={"maxWidth": "none"}),
            rx.box(s.note, class_name="sm-note"),
            class_name="sm-main",
        ),
        class_name="sm", custom_attrs={"data-state": s.state},
    )


def _journey_point(j) -> rx.Component:
    return rx.box(
        rx.box(
            rx.cond(
                j.scored,
                rx.el.i(style={"height": j.height.to_string() + "%"},
                        class_name="jp-fill"),
                rx.el.i(style={"height": "6%"}, class_name="jp-fill jp-unscored"),
            ),
            rx.cond(j.scored, rx.el.span(j.score, class_name="jp-score"),
                    rx.el.span("—", class_name="jp-score")),
            class_name="jp-bar",
        ),
        rx.box(j.words, "w", class_name="jp-words"),
        rx.box(j.label, class_name="jp-label"),
        rx.box(j.when, class_name="jp-when"),
        class_name="jp", custom_attrs={"data-current": j.current},
    )


def _next_best_edit() -> rx.Component:
    """One thing. Not a list.

    A student at one in the morning with twenty findings on screen closes the
    tab. A student with one sentence telling them what to do next, why it is
    the thing that matters, and how to start, does the thing."""
    return rx.box(
        rx.box(
            rx.el.span("Next best edit", class_name="nbe-tag"),
            rx.spacer(),
            rx.cond(EssayState.nbe_gain != "",
                    rx.el.span(EssayState.nbe_gain, class_name="nbe-gain"),
                    rx.fragment()),
            class_name="nbe-head",
        ),
        rx.box(EssayState.nbe_title, class_name="nbe-title"),
        rx.box(
            rx.el.span("Why", class_name="nbe-k"),
            rx.el.span(EssayState.nbe_why, class_name="nbe-v"),
            class_name="nbe-row",
        ),
        rx.box(
            rx.el.span("How", class_name="nbe-k"),
            rx.el.span(EssayState.nbe_how, class_name="nbe-v"),
            class_name="nbe-row",
        ),
        rx.cond(
            EssayState.nbe_idx >= 0,
            rx.el.button("Apply this fix", type="button",
                         class_name="btn btn-primary nbe-do",
                         on_click=EssayState.apply_fix(EssayState.nbe_idx)),
            rx.fragment(),
        ),
        class_name="nbe", custom_attrs={"data-kind": EssayState.nbe_kind},
    )


def _tab(key: str, label: str, count=None) -> rx.Component:
    return rx.el.button(
        rx.el.span(label, class_name="ct-lbl"),
        *( [rx.el.span(count, class_name="ct-n")] if count is not None else [] ),
        type="button", class_name="ct",
        custom_attrs={"aria-pressed": EssayState.coach_tab == key,
                      "aria-label": label},
        on_click=EssayState.set_coach_tab(key),
    )


def _pane_overview() -> rx.Component:
    return rx.box(
        rx.box(
            _dial(),
            rx.box(
                rx.cond(
                    EssayState.score_ready,
                    rx.box(
                        rx.text(EssayState.score_line, class_name="rp-line"),
                        rx.text(EssayState.confidence_line, class_name="conf-line"),
                    ),
                    rx.box(
                        rx.text(EssayState.gate_line, class_name="rp-line"),
                        rx.box(
                            rx.el.i(style={"width":
                                    EssayState.gate_percent.to_string() + "%"}),
                            class_name="cp-bar", style={"maxWidth": "none"}),
                    ),
                ),
                class_name="rp-right",
            ),
            class_name="rp-top",
        ),

        rx.box(
            _stat(EssayState.stat_words, "words"),
            _stat(EssayState.stat_sentences, "sentences"),
            _stat(EssayState.stat_avg, "avg length"),
            _stat(EssayState.stat_read, "to read"),
            class_name="rp-stats",
        ),

        # the word limit is real and discovering it late is expensive
        rx.box(
            rx.box(
                rx.el.span(EssayState.target_line, class_name="tg-line"),
                rx.spacer(),
                rx.el.span(EssayState.stat_words, " / ", EssayState.word_target,
                           class_name="tg-num"),
                class_name="tg-head",
            ),
            rx.box(rx.el.i(style={"width": EssayState.target_percent.to_string() + "%"}),
                   class_name="cp-bar", style={"maxWidth": "none"}),
            class_name="target",
            custom_attrs={"data-over": EssayState.over_limit},
        ),

        rx.cond(
            EssayState.dims.length() > 0,
            rx.box(
                rx.box("What the score is made of", class_name="pane-h"),
                rx.foreach(EssayState.dims, _dim),
                class_name="dims",
            ),
            rx.fragment(),
        ),
        class_name="pane",
    )


def _pane_problems() -> rx.Component:
    return rx.box(
        rx.box(
            rx.el.button("Check my writing", type="button",
                         class_name="btn btn-secondary",
                         on_click=EssayState.analyse_now),
            rx.el.button(EssayState.polish_label, type="button",
                         class_name="btn btn-primary",
                         disabled=~EssayState.can_polish,
                         on_click=EssayState.polish),
            rx.cond(
                EssayState.has_undo,
                rx.el.button("↩ Undo", type="button", class_name="btn btn-ghost",
                             on_click=EssayState.undo),
                rx.fragment(),
            ),
            class_name="pane-acts",
        ),
        rx.cond(
            EssayState.flash != "",
            rx.box(EssayState.flash, class_name="rp-flash"),
            rx.fragment(),
        ),
        rx.cond(
            EssayState.cats.length() > 0,
            rx.box(rx.foreach(EssayState.cats, _cat_chip), class_name="cats"),
            rx.fragment(),
        ),
        rx.cond(
            EssayState.issues.length() > 0,
            rx.box(rx.foreach(EssayState.issues, _issue), class_name="iss-list"),
            rx.box(
                rx.cond(
                    EssayState.score_ready,
                    rx.text("Nothing flagged in this draft.", class_name="faint"),
                    rx.text(EssayState.gate_line, class_name="faint"),
                ),
                class_name="pane-empty",
            ),
        ),
        class_name="pane",
    )


def _pane_strengths() -> rx.Component:
    return rx.box(
        rx.cond(
            EssayState.strengths.length() > 0,
            rx.box(
                rx.foreach(
                    EssayState.strengths,
                    lambda s: rx.box(rx.el.span("✓", class_name="gd-t"),
                                     rx.el.span(s), class_name="gd"),
                ),
                class_name="gd-list",
            ),
            rx.box(rx.text("Keep writing — these appear as the draft earns them.",
                           class_name="faint"), class_name="pane-empty"),
        ),
        rx.cond(
            EssayState.rhythm_note != "",
            rx.box(
                rx.box("Rhythm", class_name="note-tag"),
                rx.text(EssayState.rhythm_note),
                rx.cond(
                    EssayState.grade_note != "",
                    rx.text(EssayState.grade_note, class_name="faint",
                            style={"marginTop": "var(--s2)"}),
                    rx.fragment(),
                ),
                class_name="note",
            ),
            rx.fragment(),
        ),
        class_name="pane",
    )


def _pane_structure() -> rx.Component:
    return rx.box(
        rx.box(
            rx.box("The five moves", class_name="pane-h"),
            rx.text(EssayState.story_line, class_name="faint"),
            rx.box(rx.foreach(EssayState.story, _story_step), class_name="sm-list"),
            class_name="story-map",
        ),
        rx.cond(
            EssayState.paras.length() > 0,
            rx.box(
                rx.box("Paragraph shape", class_name="pane-h"),
                rx.box(rx.foreach(EssayState.paras, _para), class_name="pa-list"),
                class_name="para-shape",
            ),
            rx.fragment(),
        ),
        class_name="pane",
    )


def _pane_prompt() -> rx.Component:
    """What you are answering, and the advice that comes with it.

    The chooser is a modal (see _prompt_picker) rather than a list that unrolls
    inside this panel — eleven prompts pushed everything else off the screen,
    and on a narrow layout they landed at the very bottom of the page.
    """
    return rx.box(
        rx.box(
            rx.el.span("You are answering", class_name="pane-h"),
            rx.cond(
                EssayState.prompt_words_hint != "",
                rx.el.span(EssayState.prompt_words_hint, class_name="pq-limit"),
                rx.fragment(),
            ),
            class_name="pq-head-row",
        ),
        rx.box(EssayState.prompt, class_name="pq-full"),
        rx.cond(
            EssayState.prompt_note != "",
            rx.box(
                rx.el.span("Watch out for", class_name="pq-note-tag"),
                rx.text(EssayState.prompt_note),
                class_name="pq-advice",
            ),
            rx.fragment(),
        ),
        rx.el.button("Choose a different prompt", type="button",
                     class_name="btn btn-secondary",
                     style={"width": "100%"},
                     on_click=EssayState.open_prompts),
        class_name="pane",
    )


def _coach_panel() -> rx.Component:
    """Everything the engine has to say, in one place, behind tabs."""
    return rx.box(
        # the student's own character, reacting to the draft
        rx.box(
            coach_figure(AuthState.avatar_svg, EssayState.coach_mood),
            rx.box(
                rx.text(EssayState.coach_says, class_name="says"),
                rx.text(EssayState.coach_hint, class_name="hint"),
                # These two walk the six writing tips. They belong here, beside
                # the tip, rather than beside Save where the forward one looked
                # like "I have finished my essay".
                rx.box(
                    rx.el.button("←", type="button", class_name="tip-nav",
                                 custom_attrs={"aria-label": "Previous tip"},
                                 on_click=EssayState.back_step),
                    rx.el.span(EssayState.step_of, class_name="tip-of"),
                    rx.el.button("Next tip →", type="button",
                                 class_name="tip-nav tip-next",
                                 on_click=EssayState.next_step),
                    class_name="tip-row",
                ),
                class_name="bubble",
            ),
            class_name="coach",
        ),

        _next_best_edit(),

        rx.box(
            # "Overview", "Problems", "Strengths", "Structure" are the words a
            # teacher would use. These are the words the student would.
            _tab("overview", "Score"),
            _tab("problems", "Fixes", EssayState.total_issues),
            _tab("strengths", "Working", EssayState.strengths.length()),
            _tab("structure", "Story", EssayState.story_done),
            _tab("prompt", "Prompt"),
            class_name="ct-row",
        ),

        rx.cond(
            EssayState.coach_tab == "overview", _pane_overview(),
            rx.cond(
                EssayState.coach_tab == "problems", _pane_problems(),
                rx.cond(
                    EssayState.coach_tab == "strengths", _pane_strengths(),
                    rx.cond(
                        EssayState.coach_tab == "structure", _pane_structure(),
                        _pane_prompt(),
                    ),
                ),
            ),
        ),
        class_name="lab-coach",
        custom_attrs={"data-open": EssayState.coach_open},
        id="vg-coach",
    )


def _journey() -> rx.Component:
    """Where the draft has been.

    Three hours into a rewrite you cannot tell whether it is getting better.
    This is the only place in the app that can answer that, because it is the
    only place that remembers."""
    return rx.cond(
        EssayState.journey.length() > 1,
        rx.box(
            rx.box(
                rx.heading("Draft journey", size="4"),
                rx.spacer(),
                rx.el.button("💾 Save this version", type="button",
                             class_name="btn btn-ghost",
                             on_click=EssayState.snapshot),
                class_name="sec-head",
            ),
            rx.box(rx.foreach(EssayState.journey, _journey_point),
                   class_name="jp-row"),
            rx.cond(
                EssayState.versions.length() > 0,
                rx.box(rx.foreach(EssayState.versions, _version),
                       class_name="vr-list"),
                rx.fragment(),
            ),
            class_name="card journey",
        ),
        rx.fragment(),
    )


def essays_page() -> rx.Component:
    return shell(
        rx.box(
            # ---- header -------------------------------------------------
            rx.box(
                rx.link("← Home", href="/home", class_name="btn btn-ghost"),
                rx.box(
                    rx.heading("Essay Lab", size="5"),
                    rx.el.span(EssayState.step_of, class_name="lab-step"),
                    class_name="lab-title",
                ),
                rx.spacer(),
                rx.box(
                    rx.el.span(EssayState.save_line, class_name="faint tiny"),
                    rx.el.span(EssayState.words, " words", class_name="lab-words"),
                    rx.cond(
                        EssayState.score_ready,
                        rx.el.span(EssayState.score, class_name="lab-score",
                                   custom_attrs={"data-band": EssayState.band}),
                        rx.fragment(),
                    ),
                    class_name="lab-meta",
                ),
                rx.el.button("Coach", type="button", id="vg-coach-toggle",
                             class_name="btn btn-secondary lab-coach-btn",
                             on_click=EssayState.toggle_coach),
                class_name="lab-head",
            ),

            rx.cond(
                EssayState.just_earned != "",
                rx.box(
                    rx.box("🏆", class_name="tic"),
                    rx.box(rx.el.strong("Checkpoint reached"),
                           rx.box(EssayState.just_earned, class_name="faint")),
                    rx.spacer(),
                    rx.el.button("Nice", class_name="btn btn-ghost", type="button",
                                 on_click=EssayState.dismiss_earned),
                    class_name="toast",
                ),
                rx.fragment(),
            ),

            # ---- the question -------------------------------------------
            rx.box(
                rx.el.span("Prompt", class_name="pq-tag"),
                rx.el.span(EssayState.prompt, class_name="pq-text"),
                rx.spacer(),
                rx.el.button("Change", type="button", class_name="mini",
                             on_click=EssayState.open_prompts),
                class_name="lab-prompt",
            ),

            # ---- the workspace ------------------------------------------
            rx.box(
                rx.box(
                    _toolbar(),
                    _sprint_bar(),
                    _editor(),
                    rx.box(
                        # Filled by lab.js on every keystroke. The server's own
                        # count lags a sentence behind on purpose, which is
                        # right for the analysis and wrong for a number sitting
                        # next to the cursor.
                        rx.el.span(
                            id="vg-live", class_name="vg-live",
                            custom_attrs={
                                "data-floor": str(prose.WORDS_NO_SCORE),
                                "data-target": EssayState.word_target.to_string(),
                            }),
                        rx.spacer(),
                        # The step buttons used to be here, and the forward one
                        # was labelled "I'm done!". It does not finish the
                        # essay — it advances a coaching tip — but sitting
                        # beside Save it read as submitting the thing. Moved
                        # next to the tip it actually controls.
                        rx.el.button("Save", class_name="btn btn-primary",
                                     type="button", id="vg-save",
                                     on_click=EssayState.save),
                        class_name="editor-bar",
                    ),
                    class_name="lab-main",
                ),
                _coach_panel(),
                class_name="lab-body",
            ),

            _journey(),
            _prompt_picker(),

            rx.script(src="/essay.js"),
            rx.script(src="/lab.js"),
            class_name="screen-wrap lab",
        ),
    )


# ====================================================================
# recommendations
# ====================================================================

STAGES = [("not_asked", "Not asked"), ("asked", "Asked"),
          ("agreed", "Said yes"), ("submitted", "Letter sent")]


def _stage_picker(r) -> rx.Component:
    """Set the stage directly. The old screen could only step forward, so one
    mistaken click was stuck there forever."""
    return rx.box(
        *[
            rx.el.button(
                label, type="button", class_name="cat-chip",
                custom_attrs={"aria-pressed": r.status_key == key},
                on_click=RecsState.set_status(r.id, key),
            )
            for key, label in STAGES
        ],
        class_name="cats",
    )


def _row(r) -> rx.Component:
    return rx.box(
        rx.box(
            rx.box(
                rx.box(r.name, class_name="lr-name"),
                rx.box(
                    rx.el.span(r.subject),
                    rx.cond(r.asked != "",
                            rx.el.span(" · asked ", r.asked),
                            rx.fragment()),
                    rx.el.span(" · ", r.covers),
                    class_name="lr-sub",
                ),
            ),
            rx.box(
                rx.cond(
                    r.needs_nudge,
                    rx.box("waiting ", r.days_waiting, "d", class_name="pill pill-warn"),
                    rx.fragment(),
                ),
                rx.cond(
                    r.follow_due,
                    rx.box("chase up", class_name="pill pill-warn"),
                    rx.fragment(),
                ),
                rx.box(r.status, class_name="pill pill-neutral",
                       custom_attrs={"data-stage": r.status_key}),
                rx.el.button(rx.cond(RecsState.open_id == r.id, "▴", "▾"),
                             class_name="mini", type="button",
                             on_click=RecsState.toggle_open(r.id)),
                class_name="lr-right",
            ),
            class_name="lr-top",
        ),

        rx.cond(
            RecsState.open_id == r.id,
            rx.box(
                rx.cond(
                    r.follow_due,
                    rx.box(
                        rx.box("Follow-up due", class_name="note-tag"),
                        rx.text("You set a reminder for today. One line is "
                                "enough — they are not ignoring you, they have "
                                "forty of these."),
                        class_name="card note warn",
                        style={"marginBottom": "var(--s3)"},
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    r.needs_nudge,
                    rx.box(
                        rx.box("Follow up", class_name="note-tag"),
                        rx.text(r.nudge_text),
                        class_name="card note",
                        style={"marginBottom": "var(--s3)"},
                    ),
                    rx.fragment(),
                ),

                rx.cond(
                    r.help_text != "",
                    rx.text(r.help_text, class_name="faint",
                            style={"marginBottom": "var(--s3)"}),
                    rx.fragment(),
                ),

                _stage_picker(r),

                rx.box(
                    rx.el.label("What you want them to remember"),
                    rx.el.textarea(
                        class_name="input s-notes",
                        placeholder="The project you did in their class, the "
                                    "thing you were bad at and got better at, "
                                    "why you picked them. Give them this and "
                                    "the letter stops being generic.",
                        default_value=r.note,
                        key="rn" + r.id.to_string(),
                        on_blur=lambda v: RecsState.set_note(r.id, v),
                        rows="4",
                    ),
                    class_name="field",
                    style={"marginTop": "var(--s3)"},
                ),

                # which colleges this letter is going to
                rx.box(
                    rx.box("Which colleges is this letter for?",
                           class_name="note-tag"),
                    rx.cond(
                        r.schools.length() > 0,
                        rx.box(
                            rx.foreach(
                                r.schools,
                                lambda sc: rx.el.button(
                                    sc.name, type="button", class_name="cat-chip",
                                    custom_attrs={"aria-pressed": sc.picked},
                                    on_click=RecsState.toggle_school(r.id, sc.id),
                                ),
                            ),
                            class_name="cats",
                        ),
                        rx.text("Add colleges on the applications screen first.",
                                class_name="faint tiny"),
                    ),
                    rx.text("Leave them all off and this counts as a general "
                            "letter that goes everywhere.",
                            class_name="faint tiny",
                            style={"marginTop": "var(--s2)"}),
                    style={"marginTop": "var(--s4)"},
                ),

                # follow-up
                rx.box(
                    rx.box(
                        rx.el.label("Remind me to chase this up"),
                        rx.el.input(
                            type="date", class_name="input",
                            default_value=r.follow_up_iso,
                            key="f" + r.id.to_string() + r.follow_up_iso,
                            on_change=lambda v: RecsState.set_follow_up(r.id, v),
                        ),
                        class_name="field",
                    ),
                    rx.box(
                        rx.el.label("or"),
                        rx.el.button("In two weeks", type="button",
                                     class_name="btn btn-secondary",
                                     on_click=RecsState.remind_in_two_weeks(r.id)),
                        class_name="field",
                    ),
                    class_name="s-fields",
                ),

                rx.box(
                    rx.el.button("✉ Write the message", class_name="btn btn-primary",
                                 type="button", on_click=RecsState.start_draft(r.id)),
                    rx.spacer(),
                    rx.el.button("Remove", class_name="btn btn-ghost", type="button",
                                 on_click=RecsState.remove(r.id)),
                    style={"display": "flex", "gap": "var(--s2)",
                           "marginTop": "var(--s3)", "alignItems": "center"},
                ),

                rx.cond(
                    RecsState.draft_for == r.id,
                    rx.box(
                        rx.box("Why you're asking them", class_name="note-tag"),
                        rx.el.input(
                            class_name="input",
                            placeholder=RecsState.reason_hint,
                            default_value=RecsState.draft_reason,
                            on_change=RecsState.set_draft_reason,
                            on_blur=RecsState.rebuild_draft,
                        ),
                        rx.el.textarea(
                            class_name="input draft-box",
                            default_value=RecsState.draft_text,
                            key="d" + RecsState.draft_text.length().to_string(),
                            rows="14", id="vg-draft",
                        ),
                        rx.box(
                            rx.el.button("Copy", class_name="btn btn-secondary",
                                         type="button", id="vg-copy-draft",
                                         custom_attrs={"data-copy": "#vg-draft"}),
                            rx.el.button("Close", class_name="btn btn-ghost",
                                         type="button",
                                         on_click=RecsState.close_draft),
                            style={"display": "flex", "gap": "var(--s2)",
                                   "marginTop": "var(--s2)"},
                        ),
                        class_name="card",
                        style={"marginTop": "var(--s3)"},
                    ),
                    rx.fragment(),
                ),
                class_name="s-panel",
            ),
            rx.fragment(),
        ),
        class_name="list-row stack",
    )


def _short() -> rx.Component:
    """The question this screen exists to answer: who is still short."""
    return rx.cond(
        RecsState.short_schools.length() > 0,
        rx.box(
            rx.box("Still short of letters", class_name="note-tag"),
            rx.foreach(
                RecsState.short_schools,
                lambda n: rx.box(rx.el.span("•  "), rx.el.span(n),
                                 class_name="gd"),
            ),
            class_name="card note warn",
            style={"marginTop": "var(--s4)"},
        ),
        rx.fragment(),
    )


def _cover() -> rx.Component:
    return rx.box(
        rx.text(RecsState.cover_line, class_name="rp-line"),
        rx.box(rx.el.i(style={"width": RecsState.cover_percent.to_string() + "%"}),
               class_name="cp-bar", style={"maxWidth": "none"}),
        rx.box(
            rx.box(rx.box(RecsState.asked_count, class_name="rp-num"),
                   rx.box("asked", class_name="rp-lbl"), class_name="rp-stat"),
            rx.box(rx.box(RecsState.agreed, class_name="rp-num"),
                   rx.box("said yes", class_name="rp-lbl"), class_name="rp-stat"),
            rx.box(rx.box(RecsState.sent, class_name="rp-num"),
                   rx.box("letters in", class_name="rp-lbl"), class_name="rp-stat"),
            rx.box(rx.box(RecsState.waiting, class_name="rp-num"),
                   rx.box("gone quiet", class_name="rp-lbl"), class_name="rp-stat"),
            class_name="rp-stats",
            style={"marginTop": "var(--s4)"},
        ),
        class_name="card report",
    )


def _guide() -> rx.Component:
    return rx.box(
        rx.box(RecsState.guide_title, class_name="note-tag"),
        rx.text(RecsState.guide_when),
        rx.text(RecsState.guide_how, class_name="faint",
                style={"marginTop": "var(--s2)"}),
        class_name="card note",
        style={"marginTop": "var(--s4)"},
    )


def recommendations_page() -> rx.Component:
    return shell(
        rx.box(
            rx.box(
                rx.link("← Home", href="/home", class_name="btn btn-ghost"),
                rx.heading("Recommendations", size="5"),
                class_name="screen-head",
            ),

            rx.cond(
                RecsState.just_earned != "",
                rx.box(
                    rx.box("🏆", class_name="tic"),
                    rx.box(rx.el.strong("Checkpoint reached"),
                           rx.box(RecsState.just_earned, class_name="faint")),
                    rx.spacer(),
                    rx.el.button("Nice", class_name="btn btn-ghost", type="button",
                                 on_click=RecsState.dismiss_earned),
                    class_name="toast",
                ),
                rx.fragment(),
            ),

            # the two tabs
            rx.box(
                rx.el.button("Teacher recs", type="button",
                             custom_attrs={"aria-selected": RecsState.is_teacher_tab},
                             on_click=RecsState.set_tab("teacher")),
                rx.el.button("Guidance", type="button",
                             custom_attrs={"aria-selected": ~RecsState.is_teacher_tab},
                             on_click=RecsState.set_tab("guidance")),
                class_name="tabrow",
            ),

            _cover(),
            _short(),

            rx.text(RecsState.list_label, class_name="step-label"),
            error_box(RecsState.error),

            rx.cond(
                RecsState.rows.length() > 0,
                rx.box(rx.foreach(RecsState.rows, _row)),
                rx.box(
                    rx.text("Nobody here yet. Add the first person you plan to ask.",
                            class_name="faint"),
                    class_name="card",
                ),
            ),

            # add someone
            rx.form(
                rx.box(
                    rx.box(
                        rx.el.label("Name"),
                        rx.el.input(class_name="input", name="name",
                                    placeholder="Ms. Alvarez"),
                        class_name="field",
                    ),
                    rx.box(
                        rx.el.label("Subject"),
                        rx.el.input(class_name="input", name="subject",
                                    placeholder="AP Bio"),
                        class_name="field",
                    ),
                    rx.el.button("Add", class_name="btn btn-primary", type="submit"),
                    class_name="add-row",
                ),
                on_submit=RecsState.add,
                reset_on_submit=True,
            ),

            _guide(),
            class_name="screen-wrap",
        ),
    )
