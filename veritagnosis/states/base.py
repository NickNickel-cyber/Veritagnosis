"""
Shared plumbing for every screen's state, plus the theme picker
that every screen carries.

Merged from: base, theme_state.
"""
from __future__ import annotations

import reflex as rx
from veritagnosis import db
from veritagnosis.models import User
from veritagnosis import security as auth
from veritagnosis.states.auth_state import AuthState
import asyncio
import dataclasses
import random
from veritagnosis.content.copy import EDUCATION, QUOTES


# ====================================================================
# base
# ====================================================================

class FeatureState(rx.State, mixin=True):
    """Shared fields and the ownership check, mixed into every screen state.

    `mixin=True` is doing real work here and it is easy to get wrong.

    A plain `class FeatureState(rx.State)` with `class EssayState(FeatureState)`
    underneath does not give each screen its own copy of these fields. Reflex
    treats the subclass as a *substate*, and the fields stay on the parent —
    one `owner_id` and one `loading` shared by the essay screen, the meditation
    screen, the avatar screen and the rest. The ownership stamp would then be
    written once by whichever screen loaded first, and every other screen would
    look at it, see a match, and skip the wipe. The check would appear to work
    while doing nothing, which is worse than not having it.

    As a mixin the fields are copied into each state instead, so every screen
    carries its own stamp and clears itself independently.
    """

    loading: bool = True
    error: str = ""

    # Which user the vars on this state describe. 0 means "nobody yet".
    # Compared on every event; a mismatch wipes the state.
    owner_id: int = 0

    async def _user_id(self) -> int | None:
        """The signed-in user's id, or None.

        Validates the token every call, so a revoked or expired session stops
        working immediately, and re-checks ownership, so a state carrying the
        previous user's data is cleared before that data can be read or written.
        """
        a = await self.get_state(AuthState)
        with db.get_session() as s:
            user = auth.session_user(s, a.token)
            uid = user.id if user else None

        if uid != self.owner_id:
            # Different person (or nobody). Everything held here belongs to
            # someone else, so none of it may survive. reset() puts every var
            # back to the class default, which is the only way to be sure a
            # field added later is not forgotten here.
            self.reset()
            self.owner_id = uid or 0

        return uid

    def _forget(self) -> None:
        """Drop everything. Called when the session ends."""
        self.reset()


# ====================================================================
# theme_state
# ====================================================================

@dataclasses.dataclass(frozen=True)
class Theme:
    """Static registry entry. Rendered with a plain Python loop rather than
    rx.foreach — the list never changes at runtime, so there is nothing to
    reactively track."""

    key: str
    name: str
    blurb: str
    dark: bool
    chip_from: str
    chip_to: str


THEMES: list[Theme] = [
    Theme(key="serenity", name="Serenity", dark=False,
          blurb="Calm and soothing. Lavender, sky blue and mint.",
          chip_from="#6D5BB8", chip_to="#3D8FC4"),
    Theme(key="superhero", name="Superhero", dark=False,
          blurb="Bold and playful. Comic red, blue and dandelion yellow.",
          chip_from="#D0212B", chip_to="#1750C4"),
    Theme(key="cafe", name="Café", dark=False,
          blurb="Warm and cozy. Espresso on cream, with matcha green.",
          chip_from="#7A4E2D", chip_to="#6C8F3E"),
    Theme(key="astronomy", name="Astronomy", dark=True,
          blurb="Deep space navy and starlight.",
          chip_from="#7DAEFF", chip_to="#F2C14E"),
    Theme(key="terminal", name="Terminal", dark=True,
          blurb="Hacker green on black with electric blue.",
          chip_from="#24C46A", chip_to="#2E90FF"),
]

THEME_KEYS = [t.key for t in THEMES]
DEFAULT_THEME = "serenity"


class ThemeState(rx.State):
    # LocalStorage so the choice survives a reload before the student even has
    # an account — the wireframe puts "Choose theme" on the splash screen.
    theme: str = rx.LocalStorage(DEFAULT_THEME, name="vg_theme")

    quote_text: str = ""
    quote_source: str = ""
    edu_quotes: list[list[str]] = []

    # Same generation guard as the meditation screen: a loop started by an
    # earlier mount stops as soon as this number moves past the one it
    # captured, so navigating away and back does not leave two rotations
    # running against each other.
    quote_gen: int = 0
    rotating: bool = False

    @rx.event
    def set_theme(self, key: str):
        if key in THEME_KEYS:
            self.theme = key
            self._next_quote()

    def _next_quote(self) -> None:
        pool = QUOTES.get(self.theme, QUOTES[DEFAULT_THEME])
        choices = [q for q in pool if q[0] != self.quote_text] or pool
        text, source = random.choice(choices)
        self.quote_text = text
        self.quote_source = f"— {source}" if source else "Veritagnosis"

    @rx.event
    def reroll_quote(self):
        self._next_quote()

    @rx.event(background=True)
    async def rotate_quotes(self):
        """Rotate the line on the login screen without being asked.

        The banner is the only thing moving on a screen where somebody is
        typing a password from memory, and a login screen is looked at for
        longer than anyone admits. Nine seconds: quick enough that a second
        line lands during a typical sign-in, slow enough to read.
        """
        async with self:
            if self.rotating:
                return
            self.rotating = True
            mine = self.quote_gen

        try:
            # Bounded: a closed tab is invisible to a background task, so an
            # endless loop would rotate quotes for a browser that has gone and
            # fill the log with "delta to disconnected client". Half an hour is
            # much longer than any sign-in takes.
            for _ in range(200):
                await asyncio.sleep(9)
                async with self:
                    if mine != self.quote_gen:
                        return
                    self._next_quote()
        finally:
            async with self:
                if mine == self.quote_gen:
                    self.rotating = False

    @rx.event
    def start_quotes(self):
        """Called on mount. Rerolls once so the screen is never showing the
        same line two visits running, then starts the rotation."""
        self._next_quote()
        self.quote_gen += 1
        self.rotating = False
        return ThemeState.rotate_quotes

    @rx.event
    def load_education_quotes(self):
        """The three quotes above the signup form in the wireframe."""
        self.edu_quotes = [[t, s or ""] for t, s in EDUCATION]
        return ThemeState.start_quotes
