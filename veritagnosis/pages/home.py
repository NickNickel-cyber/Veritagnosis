"""
The home screen and the two things reached straight from it —
the checkpoint board and the avatar.

Merged from: home, achievements, avatar.
"""
from __future__ import annotations

import reflex as rx
from veritagnosis.states.auth_state import AuthState
from veritagnosis.ui.theme import btn, shell, theme_picker
from veritagnosis.states.play_state import AchievementsState
from veritagnosis.ui.theme import shell
from veritagnosis.states.play_state import AvatarState
from veritagnosis.ui.avatar import CATEGORIES


# ====================================================================
# home
# ====================================================================

TILES = [
    ("🧑‍🎨", "Avatar", "Customize your look", "/avatar"),
    ("🧭", "Profile", "Interests, activities, timeline", "/profile"),
    ("✍️", "Essays", "Write with a guide", "/essays"),
    ("🎓", "Applications", "Progress by school", "/applications"),
    ("💬", "Recommendations", "Teachers and guidance", "/recommendations"),
    ("💷", "Paying for it", "Aid, costs, scholarships", "/aid"),
    ("🧘", "Meditation", "Breathe and reset", "/meditation"),
    ("🛸", "Graze", "Fly close. 15 or 20 min", "/graze"),
    ("⚙️", "Settings", "Account and theme", "/settings"),
]


def _tile(icon: str, name: str, detail: str, route: str) -> rx.Component:
    return rx.link(
        rx.box(icon, class_name="ti"),
        rx.box(name, class_name="tn"),
        rx.box(detail, class_name="td"),
        href=route, class_name="nav-tile",
    )


def home() -> rx.Component:
    return shell(
        rx.box(
            # 1 — greeting row
            rx.box(
                rx.heading(
                    rx.el.span("Good afternoon, "),
                    rx.el.span(AuthState.display_name),
                    size="5",
                ),
                theme_picker(compact=True),
                class_name="home-greet",
            ),

            # 2 — avatar beside level and XP
            rx.box(
                rx.box(rx.html(AuthState.avatar_svg), class_name="who"),
                rx.box(
                    # data-pulse: motion.js watches the text and beats it once
                    # when it changes, so levelling up is something you see
                    # happen rather than something you notice later.
                    rx.box("Level ",
                           rx.el.span(AuthState.level,
                                      custom_attrs={"data-pulse": "1"}),
                           class_name="lvl-num"),
                    rx.box(
                        rx.box(class_name="xp-fill",
                               style={"width": AuthState.xp_percent.to_string() + "%"}),
                        class_name="xp-track",
                    ),
                    rx.box(rx.el.span(AuthState.xp_to_go,
                                      custom_attrs={"data-pulse": "1"}),
                           " xp to level ", AuthState.level + 1,
                           class_name="xp-note"),
                    class_name="lvl-block",
                ),
                class_name="home-id",
            ),

            # 3 — the bordered task box
            rx.box(
                rx.box(
                    rx.box("Your task for today", class_name="tb-label"),
                    rx.box(AuthState.task_title, class_name="tb-title"),
                    rx.box(AuthState.task_meta, class_name="tb-meta"),
                    class_name="tb-text",
                ),
                rx.link(btn("Let's go!", type="button"), href=AuthState.task_route),
                class_name="task-box",
            ),

            # 4 — checkpoints. A strip rather than a seventh tile: the sketch
            # has six tiles and this is a status line, not another destination
            # of equal weight.
            rx.cond(
                AuthState.ach_total > 0,
                rx.link(
                    rx.box(
                        rx.box(rx.cond(AuthState.ach_next_icon != "",
                                       AuthState.ach_next_icon, "🏆"),
                               class_name="bg-icon"),
                        rx.box(
                            rx.box(AuthState.ach_line, class_name="ach-line"),
                            rx.cond(
                                AuthState.ach_next != "",
                                rx.box(
                                    rx.el.span("Closest: ", class_name="faint"),
                                    rx.el.strong(AuthState.ach_next),
                                    class_name="ach-next",
                                ),
                                rx.box("Every checkpoint reached.",
                                       class_name="ach-next"),
                            ),
                            rx.box(rx.el.i(style={
                                "width": AuthState.ach_next_pct.to_string() + "%"}),
                                class_name="cp-bar", style={"maxWidth": "none"}),
                            class_name="ach-main",
                        ),
                        rx.box("›", class_name="ach-go"),
                        class_name="ach-strip",
                    ),
                    href="/achievements",
                ),
                rx.fragment(),
            ),

            # 5 — the tile grid
            rx.box(*[_tile(*t) for t in TILES], class_name="nav-grid"),

            rx.box(
                rx.el.button("Sign out", class_name="btn btn-ghost",
                             on_click=AuthState.sign_out, type="button"),
                style={"marginTop": "var(--s6)", "textAlign": "center"},
            ),
            class_name="screen-wrap",
        ),
    )


# ====================================================================
# achievements
# ====================================================================

def _badge(b) -> rx.Component:
    return rx.box(
        rx.box(rx.cond(b.reached, b.icon, "🔒"), class_name="bg-icon"),
        rx.box(
            rx.box(
                rx.el.span(b.title, class_name="bg-title"),
                rx.el.span("+", b.xp, " xp", class_name="bg-xp"),
                class_name="bg-head",
            ),
            rx.box(b.blurb, class_name="bg-blurb"),
            rx.cond(
                ~b.reached,
                rx.box(
                    rx.box(rx.el.i(style={"width": b.percent.to_string() + "%"}),
                           class_name="cp-bar", style={"maxWidth": "none"}),
                    rx.el.span(b.percent, "%", class_name="bg-pct"),
                    class_name="bg-prog",
                ),
                rx.fragment(),
            ),
            class_name="bg-main",
        ),
        class_name=rx.cond(b.reached, "bg reached",
                           rx.cond(b.is_next, "bg next", "bg")),
    )


def achievements_page() -> rx.Component:
    return shell(
        rx.box(
            rx.box(
                rx.link("← Home", href="/home", class_name="btn btn-ghost"),
                rx.heading("Checkpoints", size="5"),
                class_name="screen-head",
            ),

            # the summary
            rx.box(
                rx.box(
                    rx.box(
                        rx.box(AchievementsState.reached,
                               custom_attrs={"data-pulse": "1"},
                               class_name="dial-num"),
                        rx.box("of ", AchievementsState.total, class_name="dial-of"),
                        class_name="dial-inner",
                    ),
                    class_name="dial",
                    style={"--p": AchievementsState.percent.to_string()},
                ),
                rx.box(
                    rx.text(AchievementsState.headline, class_name="rp-line"),
                    rx.box(
                        rx.box(rx.box(AchievementsState.xp, class_name="rp-num"),
                               rx.box("xp earned", class_name="rp-lbl"),
                               class_name="rp-stat"),
                        rx.box(rx.box(AchievementsState.xp_total, class_name="rp-num"),
                               rx.box("xp on offer", class_name="rp-lbl"),
                               class_name="rp-stat"),
                        rx.box(rx.box(AchievementsState.percent, class_name="rp-num"),
                               rx.box("% complete", class_name="rp-lbl"),
                               class_name="rp-stat"),
                        class_name="rp-stats",
                    ),
                    class_name="rp-right",
                ),
                class_name="rp-top card report",
            ),

            # the closest one
            rx.cond(
                AchievementsState.next_title != "",
                rx.box(
                    rx.box(AchievementsState.next_icon, class_name="bg-icon big"),
                    rx.box(
                        rx.box("Closest to unlocking", class_name="note-tag"),
                        rx.box(AchievementsState.next_title, class_name="bg-title big"),
                        rx.box(AchievementsState.next_blurb, class_name="bg-blurb"),
                        rx.box(
                            rx.box(rx.el.i(style={
                                "width": AchievementsState.next_percent.to_string() + "%"}),
                                class_name="cp-bar", style={"maxWidth": "none"}),
                            rx.el.span(AchievementsState.next_percent, "%",
                                       class_name="bg-pct"),
                            class_name="bg-prog",
                        ),
                        class_name="bg-main",
                    ),
                    class_name="card next-up",
                ),
                rx.fragment(),
            ),

            # category filter
            rx.box(
                rx.foreach(
                    AchievementsState.cats,
                    lambda c: rx.el.button(
                        c[1], type="button", class_name="cat-chip",
                        custom_attrs={"aria-pressed":
                                      AchievementsState.filter_cat == c[0]},
                        on_click=AchievementsState.set_filter(c[0]),
                    ),
                ),
                class_name="cats",
                style={"marginTop": "var(--s5)"},
            ),

            rx.box(rx.foreach(AchievementsState.badges, _badge),
                   class_name="bg-list"),
            class_name="screen-wrap",
        ),
    )


# ====================================================================
# avatar
# ====================================================================

def _avatar_tile(o) -> rx.Component:
    return rx.el.button(
        rx.html(o.svg),
        rx.cond(
            o.locked,
            rx.box(
                rx.box("🔒", class_name="item-lock-mark"),
                rx.box(o.unlock, class_name="item-lock-text"),
                class_name="item-lock",
            ),
            rx.fragment(),
        ),
        class_name=rx.cond(o.locked, "item is-locked", "item"),
        type="button",
        custom_attrs={
            "aria-pressed": AvatarState.selected_index == o.index,
            "aria-disabled": o.locked,
            "title": rx.cond(o.locked, o.unlock + " unlocks this", o.name),
        },
        on_click=AvatarState.choose(o.index),
    )


def _swatch(c) -> rx.Component:
    return rx.el.button(
        rx.cond(c.locked, rx.box("🔒", class_name="dot-lock"), rx.fragment()),
        class_name=rx.cond(c.locked, "color-dot is-locked", "color-dot"),
        type="button",
        style={"background": c.colour},
        custom_attrs={
            "aria-pressed": AvatarState.selected_colour == c.index,
            "aria-disabled": c.locked,
            "title": rx.cond(c.locked, c.unlock + " unlocks this colour", ""),
        },
        on_click=AvatarState.choose_colour(c.index),
    )


def avatar_page() -> rx.Component:
    return shell(
        rx.box(
            rx.box(
                rx.link("← Home", href="/home", class_name="btn btn-ghost"),
                rx.heading("Customize your avatar", size="5"),
                class_name="screen-head",
            ),

            rx.box(rx.html(AvatarState.preview_svg), class_name="av-preview card"),

            # What is still shut, and how much of it.
            rx.box(
                rx.box("🔒", class_name="tic"),
                rx.box(
                    rx.el.strong("Earned with checkpoints"),
                    rx.box(AvatarState.locked_line, class_name="faint"),
                ),
                rx.spacer(),
                rx.link("See the board →", href="/achievements",
                        class_name="btn btn-ghost"),
                class_name="card note av-locknote",
            ),

            # Shown only when a locked tile was actually pressed, so the
            # explanation appears where the student is already looking.
            rx.cond(
                AvatarState.blocked != "",
                rx.box(AvatarState.blocked, class_name="auth-err av-blocked"),
                rx.fragment(),
            ),

            rx.box(
                *[
                    rx.el.button(
                        label,
                        type="button",
                        custom_attrs={"aria-selected": AvatarState.tab == key},
                        on_click=AvatarState.set_tab(key),
                    )
                    for key, label in CATEGORIES
                ],
                class_name="tabrow",
            ),

            rx.cond(
                AvatarState.palette_rows.length() > 0,
                rx.box(
                    rx.text(AvatarState.palette_label, class_name="step-label"),
                    rx.box(
                        rx.foreach(AvatarState.palette_rows, _swatch),
                        class_name="color-row",
                    ),
                    style={"marginBottom": "var(--s4)"},
                ),
                rx.fragment(),
            ),

            rx.box(
                rx.foreach(AvatarState.option_rows, _avatar_tile),
                class_name="item-grid",
            ),

            rx.box(
                rx.el.button(rx.cond(AvatarState.saved, "Saved ✓", "Save look"),
                             class_name="btn btn-primary", type="button",
                             on_click=AvatarState.save),
                rx.el.button("Surprise me", class_name="btn btn-secondary",
                             type="button", on_click=AvatarState.surprise),
                style={"display": "flex", "gap": "var(--s2)",
                       "marginTop": "var(--s5)"},
            ),
            class_name="screen-wrap",
        ),
    )
