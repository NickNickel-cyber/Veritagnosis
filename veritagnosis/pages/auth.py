"""
Getting in and out: the splash screen, sign-up, log-in, email
verification, and account settings.

Merged from: splash, login, signup, verify, settings.
"""
from __future__ import annotations

import reflex as rx
from veritagnosis.states.base import ThemeState
from veritagnosis.ui.theme import btn, shell, theme_picker
from veritagnosis.states.auth_state import AuthState
from veritagnosis.ui.theme import btn, error_box, field, shell
from veritagnosis.content.aid import GENDERS, MAX_AGE, MIN_AGE
from veritagnosis.ui.theme import btn, error_box, shell
from veritagnosis.ui.theme import shell, theme_picker


# ====================================================================
# splash
# ====================================================================

def splash() -> rx.Component:
    return shell(
        rx.box(
            rx.box(
                rx.box("V", class_name="emblem"),
                rx.heading("Veritagnosis", class_name="wordmark"),
                rx.text("College applications, one quest at a time.",
                        class_name="auth-sub", style={"maxWidth": "34ch"}),

                rx.box(
                    rx.text("Choose your theme", class_name="step-label"),
                    theme_picker(),
                    style={"width": "100%", "display": "grid", "gap": "var(--s2)",
                           "justifyItems": "center", "marginTop": "var(--s2)"},
                ),

                rx.hstack(
                    rx.link(btn("Create an account", type="button"), href="/signup"),
                    rx.link(btn("I already have one", "secondary", type="button"),
                            href="/login"),
                    spacing="3", wrap="wrap", justify="center",
                ),

                rx.text(ThemeState.quote_text, class_name="faint",
                        style={"maxWidth": "44ch"}),
                class_name="glass",
            ),
            class_name="auth-wrap",
        ),
        on_mount=ThemeState.reroll_quote,
    )


# ====================================================================
# login
# ====================================================================

def login() -> rx.Component:
    return shell(
        rx.box(
            # "College app tips or inspiring quotes" from the wireframe, drawn
            # from the active theme's pool.
            # The banner drifts and the line changes on its own. It is the
            # only thing alive on a screen somebody is typing a remembered
            # password into, and a static card there reads as a screenshot.
            # `key` is the quote itself, so React tears the node down and
            # rebuilds it on every change and the entrance animation replays
            # instead of the text swapping silently underneath.
            rx.box(
                rx.box(
                    rx.text(ThemeState.quote_text, class_name="kinetic"),
                    rx.text(ThemeState.quote_source, class_name="faint"),
                    class_name="tip-inner",
                    key=ThemeState.quote_text,
                ),
                class_name="tip-banner is-drifting",
                on_click=ThemeState.reroll_quote,
            ),
            rx.box(
                rx.heading("Welcome back", class_name="auth-title"),
                rx.text("Pick up where you left off.", class_name="auth-sub"),
                rx.cond(
                    AuthState.verified_just_now,
                    rx.box("You're signed in.",
                           class_name="note", style={"marginBottom": "var(--s4)"}),
                    rx.fragment(),
                ),
                rx.form(
                    rx.vstack(
                        error_box(AuthState.error),
                        field("Username", "username", required=True),
                        field("Password", "password", type_="password", required=True),
                        btn("Log in", type="submit"),
                        spacing="4", width="100%", align="stretch",
                    ),
                    on_submit=AuthState.handle_login,
                    reset_on_submit=False,
                ),
                rx.cond(
                    AuthState.demo_mode,
                    rx.box(
                        rx.box("Demo mode", class_name="demo-tag"),
                        rx.text("No email is configured, so sign-in codes are "
                                "shown on screen instead of being sent. Fine for "
                                "a demo; set up email before real use.",
                                class_name="demo-note"),
                        class_name="demo-banner demo-slim",
                    ),
                    rx.box(
                        "Every sign-in sends a six-digit code to your email. "
                        "Your password on its own is never enough to open your "
                        "account.",
                        class_name="faint",
                        style={"marginTop": "var(--s4)"},
                    ),
                ),
                rx.text(
                    rx.el.span("New here? "),
                    rx.link("Create an account", href="/signup"),
                    class_name="faint",
                    style={"marginTop": "var(--s2)"},
                ),
                class_name="auth-card",
                style={"marginTop": "var(--s4)"},
            ),
            class_name="auth-wrap",
        ),
        on_mount=ThemeState.start_quotes,
    )


# ====================================================================
# signup
# ====================================================================

def _quote_strip() -> rx.Component:
    return rx.box(
        rx.foreach(
            ThemeState.edu_quotes,
            lambda q: rx.box(
                rx.text(f'"{q[0]}"'),
                rx.el.span(q[1], class_name="qs"),
                class_name="quote-card",
            ),
        ),
        class_name="quote-strip",
    )


def _progress() -> rx.Component:
    return rx.box(
        *[
            rx.box(
                class_name=rx.cond(
                    AuthState.step == i, "step-dot on",
                    rx.cond(AuthState.step > i, "step-dot done", "step-dot"),
                )
            )
            for i in range(3)
        ],
        class_name="steps",
    )


def _panel(index: int, *children) -> rx.Component:
    """Mounted always, shown only on its step — so values persist."""
    return rx.box(
        *children,
        class_name="step-panel",
        style={"display": rx.cond(AuthState.step == index, "grid", "none")},
    )


def signup() -> rx.Component:
    return shell(
        rx.box(
            _quote_strip(),
            rx.box(
                _progress(),
                rx.text(AuthState.step_label, class_name="step-label"),
                rx.heading("Create your account", class_name="auth-title"),
                rx.text("One thing at a time. Nothing is saved until the end.",
                        class_name="calm-sub"),

                rx.form(
                    error_box(AuthState.error),

                    _panel(
                        0,
                        field("Username", "username",
                              "the name your future self answers to",
                              required=True, min_length=3, max_length=32),
                        field("Password", "password",
                              "a phrase is easier to remember than a word",
                              type_="password", required=True, min_length=10),
                        rx.text("At least 10 characters, with a number or symbol.",
                                class_name="faint"),
                    ),

                    _panel(
                        1,
                        field("Email", "email", "where your code will arrive",
                              type_="email", required=True),
                        rx.text("We send one six-digit code to confirm it's you. "
                                "That's the only email you'll get.",
                                class_name="faint"),
                    ),

                    _panel(
                        2,
                        rx.box(
                            rx.el.label("Age"),
                            # No default. This box used to arrive pre-filled
                            # with 17, so a student who skipped past it had an
                            # age recorded that they never entered — and age is
                            # one of the encrypted columns, stored because it
                            # is personal. A placeholder shows the format
                            # without asserting anything about them.
                            rx.el.input(class_name="input", name="age", type="number",
                                        min=MIN_AGE, max=MAX_AGE,
                                        placeholder="17"),
                            class_name="field",
                        ),
                        rx.box(
                            rx.el.label("Gender"),
                            rx.el.select(
                                rx.el.option("Prefer not to say", value=""),
                                *[rx.el.option(label, value=key)
                                  for key, label in GENDERS if key != "unspecified"],
                                class_name="input", name="gender",
                            ),
                            class_name="field",
                        ),
                        rx.text("Both are optional and only used to show you "
                                "deadlines and scholarships that actually apply.",
                                class_name="faint"),
                    ),

                    rx.box(
                        rx.cond(
                            AuthState.step > 0,
                            rx.el.button("Back", class_name="btn btn-ghost",
                                         type="button", on_click=AuthState.prev_step),
                            rx.box(style={"marginRight": "auto"}),
                        ),
                        rx.spacer(),
                        rx.cond(
                            AuthState.is_last_step,
                            rx.el.button(
                                rx.cond(AuthState.busy, "Creating…", "Create account"),
                                class_name="btn btn-primary", type="submit",
                                disabled=AuthState.busy,
                            ),
                            rx.el.button("Continue", class_name="btn btn-primary",
                                         type="button", on_click=AuthState.next_step),
                        ),
                        class_name="step-nav",
                    ),

                    on_submit=AuthState.handle_signup,
                    reset_on_submit=False,
                ),

                rx.text(
                    rx.el.span("Already have an account? "),
                    rx.link("Log in", href="/login"),
                    class_name="faint",
                    style={"marginTop": "var(--s5)"},
                ),
                class_name="auth-card",
                style={"marginTop": "var(--s5)"},
            ),
            class_name="auth-wrap",
        ),
        on_mount=[ThemeState.load_education_quotes, AuthState.reset_signup],
    )


# ====================================================================
# verify
# ====================================================================

def _box(i: int) -> rx.Component:
    return rx.box(
        rx.cond(AuthState.code.length() > i, AuthState.code[i], ""),
        class_name=rx.cond(
            AuthState.code.length() > i, "code-box filled",
            rx.cond(AuthState.code.length() == i, "code-box cursor", "code-box"),
        ),
    )


def verify() -> rx.Component:
    return shell(
        rx.box(
            rx.box(
                rx.heading("Check your email", class_name="auth-title"),
                rx.text(
                    rx.el.span("We sent six digits to "),
                    rx.el.strong(AuthState.masked_email),
                    rx.el.span(". It lasts ten minutes and works once."),
                    class_name="calm-sub",
                ),
                rx.text(
                    "This happens every time you sign in — it is what stops a "
                    "stolen password from being enough.",
                    class_name="faint",
                    style={"marginTop": "var(--s2)"},
                ),

                error_box(AuthState.error),

                rx.box(
                    *[_box(i) for i in range(6)],
                    rx.el.input(
                        class_name="code-input",
                        value=AuthState.code,
                        on_change=AuthState.set_code,
                        max_length=6,
                        input_mode="numeric",
                        auto_complete="one-time-code",
                        auto_focus=True,
                        aria_label="Verification code",
                    ),
                    class_name="code-wrap",
                    style={"marginTop": "var(--s5)"},
                ),

                rx.box(
                    btn("Let's go!", on_click=AuthState.handle_verify, type="button"),
                    style={"marginTop": "var(--s6)", "textAlign": "center"},
                ),

                rx.box(
                    rx.el.button("Send a new code", class_name="btn btn-ghost",
                                 on_click=AuthState.resend_code, type="button"),
                    style={"marginTop": "var(--s2)", "textAlign": "center"},
                ),

                # Demo mode: no mail server, so the code is shown here. Loud
                # on purpose — this must never read as normal operation.
                rx.cond(
                    AuthState.demo_code != "",
                    rx.box(
                        rx.box("Demo mode — no email configured",
                               class_name="demo-tag"),
                        rx.box(AuthState.demo_code, class_name="demo-code"),
                        rx.text(
                            "Anyone who can see this screen can sign in. Set up "
                            "email before putting real student work in here — "
                            "python scripts/manage.py email-setup",
                            class_name="demo-note",
                        ),
                        class_name="demo-banner",
                    ),
                    rx.cond(
                        AuthState.emailed,
                        rx.fragment(),
                        rx.text(
                            "We couldn't send that email. The code is printed in "
                            "the terminal window running the app.",
                            class_name="faint",
                            style={"marginTop": "var(--s5)", "textAlign": "center"},
                        ),
                    ),
                ),
                class_name="auth-card",
            ),
            class_name="auth-wrap",
        ),
    )


# ====================================================================
# settings
# ====================================================================

def settings_page() -> rx.Component:
    return shell(
        rx.box(
            rx.box(
                rx.link("← Home", href="/home", class_name="btn btn-ghost"),
                rx.heading("Settings", size="5"),
                class_name="screen-head",
            ),

            rx.box(
                rx.text("Theme", class_name="step-label"),
                theme_picker(),
                class_name="card",
                style={"marginBottom": "var(--s4)"},
            ),

            rx.box(
                rx.text("Account", class_name="step-label"),
                rx.box(
                    rx.box(rx.el.strong("Username"), rx.spacer(),
                           rx.text(AuthState.display_name),
                           style={"display": "flex"}),
                    rx.box(rx.el.strong("Level"), rx.spacer(),
                           rx.text(AuthState.level),
                           style={"display": "flex", "marginTop": "var(--s2)"}),
                    rx.box(rx.el.strong("XP"), rx.spacer(),
                           rx.text(AuthState.xp),
                           style={"display": "flex", "marginTop": "var(--s2)"}),
                ),
                rx.box(
                    rx.el.button("Sign out everywhere", class_name="btn btn-secondary",
                                 type="button", on_click=AuthState.sign_out),
                    style={"marginTop": "var(--s4)"},
                ),
                class_name="card",
            ),
            class_name="screen-wrap",
        ),
    )
