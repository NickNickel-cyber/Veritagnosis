from __future__ import annotations

import reflex as rx
from veritagnosis.states.auth_state import AuthState
from veritagnosis.states.base import THEMES, ThemeState


# theme

FONTS = [
    "https://fonts.googleapis.com/css2"
    "?family=Quicksand:wght@500;600;700"        # Serenity display
    "&family=Nunito:wght@400;600;700"           # Serenity body
    "&family=Bangers"                            # Superhero display
    "&family=Baloo+2:wght@400;600;800"          # Superhero body
    "&family=Fraunces:opsz,wght@9..144,600;9..144,800"   # Cafe display
    "&family=Lora:wght@400;600"                 # Cafe body
    "&family=Space+Grotesk:wght@500;700"        # Astronomy display
    "&family=Sora:wght@400;600"                 # Astronomy body
    "&family=JetBrains+Mono:wght@500;700"       # Terminal display
    "&family=IBM+Plex+Mono:wght@400;600"        # Terminal body
    "&display=swap",
]


class _Tokens:
    """`T.accent_soft` -> 'var(--accent-soft)'. Unknown names raise instead of
    silently emitting a var() that resolves to nothing."""

    _NAMES = {
        "bg", "surface", "surface_2", "surface_3", "border", "border_strong",
        "text", "text_dim", "text_faint",
        "accent", "accent_soft", "accent_ink", "accent_text",
        "accent_2", "accent_2_soft",
        "success", "success_soft", "success_ink",
        "warn", "warn_soft", "warn_ink",
        "danger", "danger_soft", "danger_ink",
        "xp_grad", "shadow", "glow", "motif_scene", "motif_pattern",
        "font_ui", "font_display",
        "fs_xs", "fs_sm", "fs_base", "fs_lg", "fs_xl", "fs_2xl", "fs_3xl",
        "s1", "s2", "s3", "s4", "s5", "s6", "s7",
        "r_sm", "r_md", "r_lg", "r_xl", "r_full", "ease", "dur",
    }

    def __getattr__(self, name: str) -> str:
        if name not in self._NAMES:
            raise AttributeError(
                f"unknown design token {name!r}; add it in design/build_themes.py "
                f"and to _Tokens._NAMES"
            )
        return f"var(--{name.replace('_', '-')})"


T = _Tokens()


def shell(*children, **props) -> rx.Component:
    """Root wrapper. Carries data-theme, and paints the environment behind
    everything before laying the content on top of it."""
    attrs = {"data-theme": ThemeState.theme, **props.pop("custom_attrs", {})}
    return rx.box(
        scene(),
        rx.box(*children, class_name="vg-content"),
        _watchdog(),
        rx.script(src="/motion.js"),
        class_name="vg-app",
        custom_attrs=attrs,
        **props,
    )


def _watchdog() -> rx.Component:
    return rx.fragment(
        rx.el.button(
            "", id="vg-beat-btn", type="button",
            on_click=AuthState.heartbeat,
            aria_hidden="true", tab_index=-1,
            style={"position": "absolute", "width": "1px", "height": "1px",
                   "opacity": 0, "pointerEvents": "none", "left": "-9999px"},
        ),
        rx.el.span(
            AuthState.beat, id="vg-beat", aria_hidden="true",
            style={"position": "absolute", "left": "-9999px",
                   "width": "1px", "height": "1px", "overflow": "hidden"},
        ),
        rx.el.div(
            rx.el.span("Lost the connection to the app.", class_name="conn-msg"),
            rx.el.span("Reconnecting…", class_name="conn-sub"),
            rx.el.button("Reload now", id="vg-reload", type="button",
                         class_name="btn btn-primary"),
            id="vg-conn", class_name="conn-banner", hidden=True,
            role="status", aria_live="polite",
        ),
    )


def theme_picker(compact: bool = False) -> rx.Component:
    """Theme chips. `compact` is the small "Theme" control in the home header."""
    chips = [
        rx.el.button(
            rx.box(class_name="dot",
                   style={"background": f"linear-gradient(135deg,{t.chip_from},{t.chip_to})"}),
            rx.cond(compact, "", t.name),
            class_name="tswatch",
            custom_attrs={"aria-pressed": ThemeState.theme == t.key},
            on_click=ThemeState.set_theme(t.key),
            type="button",
        )
        for t in THEMES
    ]
    return rx.hstack(*chips, spacing="2", wrap="wrap", justify="center")


def hero(on_click=None) -> rx.Component:
    return rx.box(
        rx.box(
            rx.text(f'"{ThemeState.quote_text}"', class_name="hero-quote kinetic",
                    key=ThemeState.quote_text),
            rx.text(ThemeState.quote_source, class_name="hero-by"),
            class_name="hero-plate quote-wrap",
        ),
        class_name="hero",
        on_click=on_click or ThemeState.reroll_quote,
    )


# Small shared pieces
def field(label: str, name: str, placeholder: str = "", type_: str = "text",
          **props) -> rx.Component:
    """A labelled input inside an rx.form. `name` is what the submit handler
    receives — password fields never bind to a State var."""
    return rx.box(
        rx.el.label(label),
        rx.el.input(class_name="input", name=name, placeholder=placeholder,
                    type=type_, **props),
        class_name="field",
    )


def error_box(message) -> rx.Component:
    return rx.cond(message != "", rx.box(message, class_name="auth-err"), rx.fragment())


def btn(label, variant: str = "primary", **props) -> rx.Component:
    return rx.el.button(label, class_name=f"btn btn-{variant}", **props)


# scene

_MOTES = [
    (8, 7, 34, 0), (23, 4, 46, 6), (41, 9, 39, 13),
    (58, 5, 52, 3), (72, 8, 42, 19), (88, 5, 48, 9), (95, 3, 58, 24),
]


def scene() -> rx.Component:
    return rx.fragment(
        rx.box(
            rx.box(class_name="lyr lyr-sky"),
            rx.box(class_name="lyr lyr-mid"),
            rx.box(class_name="lyr lyr-near"),
            class_name="scene",
            aria_hidden="true",
        ),
        rx.box(
            *[
                rx.box(
                    class_name="mote",
                    style={
                        "left": f"{left}%",
                        "width": f"{size}px",
                        "height": f"{size}px",
                        "animationDuration": f"{dur}s",
                        "animationDelay": f"-{delay}s",
                    },
                )
                for left, size, dur, delay in _MOTES
            ],
            class_name="motes",
            aria_hidden="true",
        ),
    )
