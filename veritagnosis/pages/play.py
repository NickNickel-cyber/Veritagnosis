from __future__ import annotations

import reflex as rx
from veritagnosis.states.play_state import MeditationState
from veritagnosis.ui.widgets import DURATIONS, PATTERNS
from veritagnosis.ui.theme import shell
from veritagnosis.states.play_state import GrazeState
from veritagnosis.ui import widgets as content


# meditation

def _technique_row(p: dict) -> rx.Component:
    """One of the stacked rows in the sketch — a whole technique per row."""
    icons = {"box": "⬜", "478": "🌙", "468": "🫧"}
    return rx.el.button(
        rx.box(icons.get(p["key"], "🫧"), class_name="sr-ic"),
        rx.box(
            rx.box(p["name"], class_name="sr-name"),
            rx.box(p["blurb"], class_name="sr-sub"),
        ),
        class_name="stack-row",
        type="button",
        custom_attrs={"aria-pressed": MeditationState.pattern == p["key"]},
        on_click=MeditationState.set_pattern(p["key"]),
    )


def _checkpoint(cp) -> rx.Component:
    return rx.box(
        rx.box(rx.cond(cp.reached, "✓", cp.icon), class_name="cp-dot"),
        rx.box(
            rx.box(cp.title, class_name="cp-title"),
            rx.box(cp.blurb, class_name="cp-blurb"),
            rx.cond(
                cp.is_next,
                rx.box(rx.el.i(style={"width": cp.percent.to_string() + "%"}),
                       class_name="cp-bar"),
                rx.fragment(),
            ),
            class_name="cp-body",
        ),
        rx.box("+", cp.xp, " xp", class_name="cp-xp"),
        class_name=rx.cond(cp.reached, "cp reached",
                           rx.cond(cp.is_next, "cp next", "cp")),
    )


def meditation_page() -> rx.Component:
    return shell(
        rx.box(
            rx.box(
                rx.link("← Home", href="/home", class_name="btn btn-ghost"),
                rx.heading("Meditation", size="5"),
                class_name="screen-head",
            ),

            rx.box(
                rx.text(f'"{MeditationState.quote_text}"',
                        class_name="med-quote kinetic",
                        key=MeditationState.quote_text),
                rx.box(
                    rx.text(MeditationState.quote_source, class_name="faint"),
                    style={"display": "flex", "alignItems": "baseline",
                           "gap": "var(--s3)"},
                ),
                class_name="card quote-wrap med-quote-card",
                style={"marginBottom": "var(--s5)", "cursor": "pointer"},
                on_click=MeditationState.reroll_quote,
            ),

            # the stacked technique rows
            rx.text("Choose a technique", class_name="step-label"),
            *[_technique_row(p) for p in PATTERNS],

            # session length
            rx.text("How long", class_name="step-label",
                    style={"marginTop": "var(--s4)"}),
            rx.box(
                *[
                    rx.el.button(
                        f"{m} min", type="button",
                        custom_attrs={"aria-pressed": MeditationState.minutes == m},
                        on_click=MeditationState.set_minutes(m),
                    )
                    for m in DURATIONS
                ],
                class_name="seg",
            ),

            rx.box(
                rx.box(class_name="breath-figure", id="breath-figure"),
                rx.box(
                    rx.box("4", class_name="phase-count", id="breath-count"),
                    rx.box("Breathe in", class_name="phase-label", id="breath-phase"),
                    class_name="breath-readout",
                ),
                class_name="breath-stage",
                style={"marginTop": "var(--s4)"},
            ),
            rx.box(rx.el.i(id="breath-progress", style={"width": "0%"}),
                   class_name="breath-progress"),
            rx.box(
                # The label lives in its own span so the browser script can
                # flip Start/Pause without touching anything Reflex renders.
                rx.el.button(
                    rx.el.span("Start", class_name="b-play-label"),
                    class_name="btn btn-primary", type="button", id="breath-play"),
                rx.el.button("Reset", class_name="btn btn-secondary", type="button",
                             id="breath-reset"),
                style={"display": "flex", "gap": "var(--s2)",
                       "marginTop": "var(--s3)"},
            ),
            rx.el.button(
                "", id="breath-finish", type="button",
                on_click=MeditationState.finish_session,
                style={"display": "none"}, aria_hidden="true",
            ),
            rx.script(src="/breathing.js"),

            # the roadmap
            rx.box(
                rx.box(
                    rx.heading("Your roadmap", size="4"),
                    rx.spacer(),
                    rx.text(MeditationState.reached_count, " of ",
                            MeditationState.checkpoints.length(), class_name="faint"),
                    style={"display": "flex", "alignItems": "baseline",
                           "gap": "var(--s3)", "marginBottom": "var(--s2)"},
                ),
                rx.box(rx.el.i(style={"width": MeditationState.roadmap_percent.to_string() + "%"}),
                       class_name="cp-bar", style={"maxWidth": "none"}),
                rx.box(
                    rx.foreach(MeditationState.checkpoints, _checkpoint),
                    class_name="road",
                ),
                class_name="card",
                style={"marginTop": "var(--s6)"},
            ),

            # celebration when a checkpoint is crossed
            rx.cond(
                MeditationState.just_unlocked != "",
                rx.box(
                    rx.box("🎉", class_name="tic"),
                    rx.box(
                        rx.el.strong("Checkpoint reached"),
                        rx.box(MeditationState.just_unlocked, class_name="faint"),
                    ),
                    rx.spacer(),
                    rx.el.button("Nice", class_name="btn btn-ghost", type="button",
                                 on_click=MeditationState.dismiss_unlock),
                    class_name="toast",
                    style={"marginTop": "var(--s4)"},
                ),
                rx.fragment(),
            ),

            # data-pulse: motion.js watches these numbers and beats them once
            # when they change, so finishing a sitting visibly moves something.
            rx.box(
                rx.el.span(MeditationState.sessions, custom_attrs={"data-pulse": "1"}),
                rx.el.span(" sessions · "),
                rx.el.span(MeditationState.total_minutes,
                           custom_attrs={"data-pulse": "1"}),
                rx.el.span(" minutes · "),
                rx.el.span(MeditationState.streak, custom_attrs={"data-pulse": "1"}),
                rx.el.span(" day streak"),
                class_name="faint med-stats",
                style={"marginTop": "var(--s4)", "textAlign": "center",
                       "display": "block"},
            ),
            class_name="screen-wrap",
        ),
        # tells the browser script which pattern and length are selected
        custom_attrs={
            "data-pattern": MeditationState.pattern,
            "data-minutes": MeditationState.minutes.to_string(),
        },
    )


# graze

THEME_BLURBS = [(k, v["name"], v["blurb"]) for k, v in content.THEMES.items()]


def _menu() -> rx.Component:
    return rx.box(
        rx.box(
            rx.text(("You don't have a weapon. Fly close to things without touching them "
                     'to charge up.'), class_name="rp-line"),
            rx.box(
                rx.box(
                    rx.el.b("Move"),
                    rx.el.span(': the ship follows your mouse. WASD and the arrow keys work too.'),
                    class_name="gz-rule",
                ),
                rx.box(
                    rx.el.b("Graze"),
                    rx.el.span((': skim past a shape without touching it. Your ring fills and time '
                                'slows for a moment.')),
                    class_name="gz-rule",
                ),
                rx.box(
                    rx.el.b("Burst"),
                    rx.el.span((': when your ring is full, click, tap or press space to clear '
                                'everything near you.')),
                    class_name="gz-rule",
                ),
                rx.box(
                    rx.el.b("You can't lose"),
                    rx.el.span((': if you get hit, the run restarts and the session timer keeps '
                                'going. Every fourth wave brings a Guardian.')),
                    class_name="gz-rule",
                ),
                class_name="gz-rules",
            ),
            class_name="card report",
        ),

        rx.box(
            rx.text("How long", class_name="step-label"),
            rx.box(
                *[
                    rx.el.button(
                        f"{m} minutes", type="button",
                        custom_attrs={"aria-pressed": GrazeState.minutes == m},
                        on_click=GrazeState.choose(m),
                    )
                    for m in content.LENGTHS
                ],
                class_name="seg",
            ),
            rx.box(
                rx.el.button(
                    "Start", class_name="btn btn-primary",
                    type="button",
                    custom_attrs={"data-graze-start": GrazeState.minutes.to_string()},
                    on_click=GrazeState.begin,
                ),
                style={"marginTop": "var(--s4)"},
            ),
            style={"marginTop": "var(--s5)"},
        ),

        rx.box(
            rx.text(GrazeState.history_line, class_name="faint"),
            style={"marginTop": "var(--s5)", "textAlign": "center"},
        ),
    )


def _stage() -> rx.Component:
    return rx.box(
        # session clock
        rx.box(
            rx.el.span("⏱", class_name="sp-ic"),
            rx.el.span("0:00", id="gz-time", class_name="sp-time"),
            rx.spacer(),
            rx.el.span("", id="gz-combo", class_name="gz-combo"),
            rx.el.button("End early", id="gz-stop", type="button",
                         class_name="btn btn-ghost",
                         on_click=GrazeState.quit_early),
            class_name="sprint gz-clock",
        ),
        rx.box(rx.el.i(id="gz-timefill", style={"width": "100%"}),
               class_name="cp-bar", style={"maxWidth": "none"}),

        # the stage
        rx.box(
            rx.el.canvas(id="gz-canvas"),
            rx.box(
                rx.box(
                    rx.el.span("score ", class_name="faint"),
                    rx.el.span("0", id="gz-score", class_name="gz-num"),
                    class_name="gz-stat",
                ),
                rx.box(
                    rx.el.span("wave ", class_name="faint"),
                    rx.el.span("1", id="gz-wave", class_name="gz-num"),
                    class_name="gz-stat",
                ),
                rx.box(
                    rx.el.span("run ", class_name="faint"),
                    rx.el.span("1", id="gz-run", class_name="gz-num"),
                    class_name="gz-stat",
                ),
                rx.box(id="gz-shields", class_name="gz-shields"),
                class_name="gz-hud",
            ),
            rx.el.div(rx.el.i(id="gz-bossfill"), id="gz-bossbar",
                      class_name="gz-bossbar", hidden=True),
            rx.el.div("", id="gz-respawn", class_name="gz-respawn", hidden=True),
            rx.el.div(
                rx.el.div('Wave cleared! Pick an upgrade', class_name="gz-draft-h"),
                rx.el.div(id="gz-cards", class_name="gz-cards"),
                id="gz-draft", class_name="gz-draft", hidden=True,
            ),
            id="gz-stage", class_name="gz-stage",
        ),

        # how the browser hands the result back to Python
        rx.form(
            rx.el.input(type="hidden", name="score", id="gz-out-score"),
            rx.el.input(type="hidden", name="minutes", id="gz-out-minutes"),
            rx.el.input(type="hidden", name="wave", id="gz-out-wave"),
            rx.el.input(type="hidden", name="runs", id="gz-out-runs"),
            rx.el.input(type="hidden", name="chain", id="gz-out-chain"),
            rx.el.button("", id="gz-finish", type="submit",
                         aria_hidden="true", tab_index=-1,
                         style={"display": "none"}),
            on_submit=GrazeState.finish,
        ),
    )


def _done() -> rx.Component:
    return rx.box(
        rx.box(
            rx.box(
                rx.box(GrazeState.last_score, custom_attrs={"data-pulse": "1"},
                       class_name="dial-num"),
                rx.box("points", class_name="dial-of"),
                class_name="dial-inner",
            ),
            class_name="dial",
            style={"--p": "100"},
        ),
        rx.box(
            rx.text(GrazeState.closing, class_name="rp-line"),
            rx.box(
                rx.box(rx.box(GrazeState.last_wave, class_name="rp-num"),
                       rx.box("best wave", class_name="rp-lbl"), class_name="rp-stat"),
                rx.box(rx.box(GrazeState.last_runs, class_name="rp-num"),
                       rx.box("runs", class_name="rp-lbl"), class_name="rp-stat"),
                rx.box(rx.box("×", GrazeState.last_chain, class_name="rp-num"),
                       rx.box("best chain", class_name="rp-lbl"), class_name="rp-stat"),
                rx.box(rx.box("+", GrazeState.gained_xp, class_name="rp-num"),
                       rx.box("xp", class_name="rp-lbl"), class_name="rp-stat"),
                class_name="rp-stats",
            ),
            rx.box(
                rx.el.button("Go again", class_name="btn btn-primary", type="button",
                             on_click=GrazeState.again),
                rx.link(rx.el.button("Back to work", class_name="btn btn-ghost",
                                     type="button"), href="/home"),
                style={"display": "flex", "gap": "var(--s2)",
                       "marginTop": "var(--s4)"},
            ),
            class_name="rp-right",
        ),
        class_name="card report rp-top",
    )


def graze_page() -> rx.Component:
    return shell(
        rx.box(
            rx.box(
                rx.link("← Home", href="/home", class_name="btn btn-ghost"),
                rx.heading("Graze", size="5"),
                class_name="screen-head",
            ),

            rx.cond(
                GrazeState.just_earned != "",
                rx.box(
                    rx.box("🏆", class_name="tic"),
                    rx.box(rx.el.strong("Checkpoint reached"),
                           rx.box(GrazeState.just_earned, class_name="faint")),
                    rx.spacer(),
                    rx.el.button("Nice", class_name="btn btn-ghost", type="button",
                                 on_click=GrazeState.dismiss_earned),
                    class_name="toast",
                ),
                rx.fragment(),
            ),

            rx.cond(
                GrazeState.started,
                _stage(),
                rx.cond(GrazeState.finished, _done(), _menu()),
            ),

            rx.script(src="/graze.js"),
            class_name="screen-wrap",
        ),
    )
