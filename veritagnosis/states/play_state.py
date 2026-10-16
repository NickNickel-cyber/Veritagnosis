"""
The screens that are not the application: avatar, meditation,
Graze, and the checkpoint board.

Merged from: avatar_state, meditation_state, graze_state, achievements_state.
"""
from __future__ import annotations

import dataclasses
import json
import random
import reflex as rx
from veritagnosis import db
from veritagnosis.content import achievements as ach_content
from veritagnosis.models import User
from veritagnosis.services import wellbeing as achievements
from veritagnosis.states.base import FeatureState
from veritagnosis.ui import avatar as parts
import asyncio
from datetime import timedelta
from sqlmodel import select
from veritagnosis.content import copy as roadmap
from veritagnosis.models import CheckpointProgress, MeditationLog, User, utcnow
from veritagnosis.ui.widgets import DURATIONS, PATTERNS
from veritagnosis.services import wellbeing as achievements, wellbeing as breaks
from veritagnosis.services import wellbeing as achievements, apply as progress

# Two sections of this file each had a module aliased to `content`, and they
# were different modules. Merged into one file the second binding silently
# won, and the Graze screen started reading the checkpoint content. They get
# distinct names here so neither can shadow the other again.
from veritagnosis.ui import widgets as graze_content


# ====================================================================
# avatar_state
# ====================================================================

@dataclasses.dataclass
class OptionRow:
    """One tile in the grid."""

    index: int
    name: str
    svg: str
    locked: bool
    unlock: str          # "Send an application" — empty when it was never shut


@dataclasses.dataclass
class ColourRow:
    index: int
    colour: str
    locked: bool
    unlock: str


class AvatarState(FeatureState, rx.State):
    tab: str = "head"
    selection: dict[str, int] = {}
    saved: bool = False
    earned: list[str] = []
    blocked: str = ""      # set when a locked tile is pressed, cleared on move

    # ---------------------------------------------------------------- helpers
    def _unlock_text(self, key: str | None) -> str:
        if not key:
            return ""
        a = ach_content.BY_KEY.get(key)
        return a["title"] if a else ""

    @rx.var
    def preview_svg(self) -> str:
        return parts.render(self.selection, 300)

    @rx.var(cache=True)
    def option_rows(self) -> list[OptionRow]:
        """Each tile shows the whole avatar with only this one part swapped, so
        you judge the choice in context instead of seeing a floating body part.

        A locked tile still renders its preview. Seeing the thing you have not
        got is the entire motivation; a grey square is just a grey square.
        """
        got = set(self.earned)
        names = parts.OPTIONS.get(self.tab, [])
        rows = []
        for i, name in enumerate(names):
            preview = dict(self.selection)
            preview[self.tab] = i
            need = parts.lock_for(self.tab, i)
            rows.append(OptionRow(
                index=i, name=name, svg=parts.render(preview, 96),
                locked=not parts.is_available(self.tab, i, got),
                unlock=self._unlock_text(need),
            ))
        return rows

    @rx.var(cache=True)
    def palette_rows(self) -> list[ColourRow]:
        """Skin swatches on the Head tab, hair colours on the Hair tab."""
        got = set(self.earned)
        if self.tab == "head":
            # Skin tone is identity, never a reward. Nothing here is ever shut.
            return [ColourRow(index=i, colour=c, locked=False, unlock="")
                    for i, c in enumerate(parts.SKIN_TONES)]
        if self.tab == "hair":
            out = []
            for i, c in enumerate(parts.HAIR_COLORS):
                need = parts.colour_lock_for(i)
                out.append(ColourRow(index=i, colour=c,
                                     locked=bool(need) and need not in got,
                                     unlock=self._unlock_text(need)))
            return out
        return []

    @rx.var
    def selected_index(self) -> int:
        return self.selection.get(self.tab, 0)

    @rx.var
    def selected_colour(self) -> int:
        return self.selection.get(self.palette_key, 0)

    @rx.var
    def palette_key(self) -> str:
        return "skin" if self.tab == "head" else "hair_color"

    @rx.var
    def palette_label(self) -> str:
        return "Skin tone" if self.tab == "head" else "Hair colour"

    @rx.var(cache=True)
    def locked_count(self) -> int:
        got = set(self.earned)
        n = sum(1 for (c, i), k in parts.LOCKED.items() if k not in got)
        n += sum(1 for k in parts.LOCKED_COLOURS.values() if k not in got)
        return n

    @rx.var(cache=True)
    def locked_line(self) -> str:
        n = self.locked_count
        total = len(parts.LOCKED) + len(parts.LOCKED_COLOURS)
        if n == 0:
            return f"All {total} unlockable items are yours."
        if n == total:
            return f"{total} more items unlock as you reach checkpoints."
        return f"{total - n} of {total} unlockable items earned. {n} to go."

    # ------------------------------------------------------------------ load
    @rx.event
    async def load(self):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        with db.get_session() as s:
            # Award first: arriving here straight after finishing something
            # should show the reward already unlocked, not one visit later.
            achievements.award(s, uid)
            self.earned = sorted(achievements.reached_keys(s, uid))
            user = s.get(User, uid)
            try:
                sel = {**parts.DEFAULT_AVATAR, **json.loads(user.avatar or "{}")}
            except (ValueError, TypeError):
                sel = dict(parts.DEFAULT_AVATAR)
            self.selection = parts.sanitise(sel, set(self.earned))
        self.blocked = ""
        self.loading = False

    # ---------------------------------------------------------------- events
    @rx.event
    def set_tab(self, tab: str):
        if tab in parts.OPTIONS:
            self.tab = tab
        self.saved = False
        self.blocked = ""

    @rx.event
    def choose(self, index: int):
        if not parts.is_available(self.tab, index, set(self.earned)):
            need = self._unlock_text(parts.lock_for(self.tab, index))
            self.blocked = f"“{need}” unlocks that one." if need else 'Not unlocked yet.'
            return
        self.selection = {**self.selection, self.tab: index}
        self.saved = False
        self.blocked = ""

    @rx.event
    def choose_colour(self, index: int):
        if self.palette_key == "hair_color":
            need = parts.colour_lock_for(index)
            if need and need not in set(self.earned):
                self.blocked = f"“{self._unlock_text(need)}” unlocks that color."
                return
        self.selection = {**self.selection, self.palette_key: index}
        self.saved = False
        self.blocked = ""

    @rx.event
    def surprise(self):
        """Random, but only from what has actually been earned — a surprise
        that hands you something locked and then refuses to save it would be
        a small cruelty."""
        got = set(self.earned)
        pick = {}
        for cat, opts in parts.OPTIONS.items():
            allowed = [i for i in range(len(opts))
                       if parts.is_available(cat, i, got)]
            pick[cat] = random.choice(allowed)
        pick["skin"] = random.randrange(len(parts.SKIN_TONES))
        colours = [i for i in range(len(parts.HAIR_COLORS))
                   if not parts.colour_lock_for(i)
                   or parts.colour_lock_for(i) in got]
        pick["hair_color"] = random.choice(colours)
        self.selection = {**self.selection, **pick}
        self.saved = False
        self.blocked = ""

    @rx.event
    async def save(self):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        with db.get_session() as s:
            user = s.get(User, uid)
            if user:
                # Sanitised on the way out as well as the way in: the blob
                # outlives the rules that produced it.
                clean = parts.sanitise(self.selection, set(self.earned))
                user.avatar = json.dumps(clean)[:512]
                s.add(user)
                s.commit()
            # Customising the avatar is itself a checkpoint.
            achievements.award(s, uid)
            self.earned = sorted(achievements.reached_keys(s, uid))
        self.saved = True


# ====================================================================
# meditation_state
# ====================================================================

@dataclasses.dataclass
class Checkpoint:
    key: str
    title: str
    blurb: str
    icon: str
    xp: int
    reached: bool
    is_next: bool
    percent: int


class MeditationState(FeatureState, rx.State):
    pattern: str = "box"
    minutes: int = 2

    sessions: int = 0
    total_minutes: int = 0
    streak: int = 0
    patterns_tried: int = 0

    checkpoints: list[Checkpoint] = []
    just_unlocked: str = ""
    quote_text: str = ""
    quote_source: str = ""

    # Bumped on every load. The rotating task carries the value it started
    # with and stops as soon as it stops matching, which is how a loop from
    # a previous visit to this screen dies instead of stacking up with the
    # new one and making the quote flicker twice as fast.
    quote_gen: int = 0
    rotating: bool = False

    @rx.var
    def pattern_name(self) -> str:
        return next((p["name"] for p in PATTERNS if p["key"] == self.pattern), "")

    @rx.var
    def reached_count(self) -> int:
        return sum(1 for c in self.checkpoints if c.reached)

    @rx.var
    def roadmap_percent(self) -> int:
        total = len(roadmap.ROADMAP)
        return int(100 * self.reached_count / total) if total else 0

    def _next_quote(self) -> None:
        """Pick a different one. Never the line already showing, or a reroll
        occasionally looks like nothing happened."""
        pool = [q for q in roadmap.MEDITATION_QUOTES if q[0] != self.quote_text] or roadmap.MEDITATION_QUOTES
        text, src = random.choice(pool)
        self.quote_text = text
        self.quote_source = f"— {src}" if src else "Veritagnosis"

    @rx.event
    def reroll_quote(self):
        """Another quote. Tapping the card runs this, and because the text
        changes, motion.js re-splits it and the word-by-word reveal replays —
        which is the whole reason the card is tappable."""
        self._next_quote()

    @rx.event(background=True)
    async def rotate_quotes(self):
        """Change the line on its own every so often.

        Tapping the card already worked, but a card that only changes when
        you tap it is a card that never changes, because nobody knows it is
        tappable. This screen is one a student sits in front of doing
        nothing on purpose, so the reading material should move.

        Eleven seconds is long enough to read a line twice and short enough
        that you see it happen at least once while a two-minute breathing
        session runs.
        """
        async with self:
            if self.rotating:
                return
            self.rotating = True
            mine = self.quote_gen

        try:
            # Bounded rather than infinite. Closing the tab does not tell the
            # server anything a background task can see, so an endless loop
            # keeps rotating a quote for a browser that left and fills the log
            # with "delta to disconnected client". Roughly forty minutes is
            # far longer than anyone sits on this screen, and coming back
            # mounts the page again and starts a fresh one.
            for _ in range(220):
                await asyncio.sleep(11)
                async with self:
                    if mine != self.quote_gen:
                        return          # a newer visit owns the screen now
                    self._next_quote()
        finally:
            async with self:
                if mine == self.quote_gen:
                    self.rotating = False

    @rx.event
    def set_pattern(self, key: str):
        self.pattern = key

    @rx.event
    def set_minutes(self, m: int):
        self.minutes = m

    @rx.event
    async def load(self):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        text, src = random.choice(roadmap.MEDITATION_QUOTES)
        self.quote_text, self.quote_source = text, (f"— {src}" if src else "Veritagnosis")
        self._recompute(uid)
        self.loading = False
        # Retire any rotation left over from a previous visit, then start one.
        self.quote_gen += 1
        self.rotating = False
        return MeditationState.rotate_quotes

    # ------------------------------------------------------------------ stats
    def _stats(self, uid: int) -> dict:
        with db.get_session() as s:
            logs = s.exec(select(MeditationLog)
                          .where(MeditationLog.user_id == uid)
                          .order_by(MeditationLog.finished_at.desc())).all()
        days = sorted({l.finished_at.date() for l in logs}, reverse=True)
        streak, today = 0, utcnow().date()
        # A streak counts back from today or yesterday, so sitting last night
        # still counts this morning.
        if days and (today - days[0]).days <= 1:
            streak, cursor = 1, days[0]
            for d in days[1:]:
                if (cursor - d).days == 1:
                    streak += 1; cursor = d
                else:
                    break
        return {
            "sessions": len(logs),
            "minutes": sum(l.minutes for l in logs),
            "streak": streak,
            "patterns": len({l.pattern for l in logs}),
        }

    def _recompute(self, uid: int) -> None:
        stats = self._stats(uid)
        self.sessions = stats["sessions"]
        self.total_minutes = stats["minutes"]
        self.streak = stats["streak"]
        self.patterns_tried = stats["patterns"]

        with db.get_session() as s:
            reached = {r.checkpoint_key for r in s.exec(
                select(CheckpointProgress)
                .where(CheckpointProgress.user_id == uid)).all()}
        nxt = roadmap.next_checkpoint(stats)
        self.checkpoints = [
            Checkpoint(
                key=c["key"], title=c["title"], blurb=c["blurb"],
                icon=c["icon"], xp=c["xp"],
                reached=c["key"] in reached,
                is_next=bool(nxt and c["key"] == nxt["key"]),
                percent=roadmap.progress_to(c, stats) if nxt and c["key"] == nxt["key"]
                        else (100 if c["key"] in reached else 0),
            )
            for c in roadmap.ROADMAP
        ]

    # -------------------------------------------------------------- finishing
    @rx.event
    async def finish_session(self):
        """Called when the timer runs out. Logs the sitting, then awards any
        checkpoint the new totals have just satisfied."""
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")

        with db.get_session() as s:
            s.add(MeditationLog(user_id=uid, pattern=self.pattern,
                                minutes=self.minutes, kind="breathing"))
            s.commit()

        stats = self._stats(uid)
        newly = []
        with db.get_session() as s:
            already = {r.checkpoint_key for r in s.exec(
                select(CheckpointProgress)
                .where(CheckpointProgress.user_id == uid)).all()}
            user = s.get(User, uid)
            for key in roadmap.unlocked(stats):
                if key in already:
                    continue
                s.add(CheckpointProgress(user_id=uid, checkpoint_key=key))
                cp = next(c for c in roadmap.ROADMAP if c["key"] == key)
                newly.append(cp["title"])
                if user:
                    user.xp += cp["xp"]
            # A sitting is worth XP whether or not it crossed a checkpoint.
            if user:
                user.xp += 10 * self.minutes
                s.add(user)
            s.commit()

        self.just_unlocked = newly[0] if newly else ""
        self._recompute(uid)

    @rx.event
    def dismiss_unlock(self):
        self.just_unlocked = ""


# ====================================================================
# graze_state
# ====================================================================

class GrazeState(FeatureState, rx.State):
    minutes: int = 15
    started: bool = False
    finished: bool = False

    # what the last session came to
    last_score: int = 0
    last_wave: int = 1
    last_runs: int = 1
    last_chain: int = 1
    gained_xp: int = 0
    closing: str = ""

    # lifetime
    sessions: int = 0
    total_minutes: int = 0
    best_score: int = 0

    just_earned: str = ""

    @rx.var
    def lengths(self) -> list[int]:
        return list(graze_content.LENGTHS)

    @rx.var(deps=["sessions", "total_minutes"])
    def history_line(self) -> str:
        if not self.sessions:
            return "No sessions yet."
        return (f"{self.sessions} "
                f"{'session' if self.sessions == 1 else 'sessions'} · "
                f"{self.total_minutes} minutes · best {self.best_score:,}")

    @rx.event
    async def load(self):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")
        with db.get_session() as s:
            st = breaks.stats(s, uid, "graze")
        self.sessions = st["sessions"]
        self.total_minutes = st["minutes"]
        self.best_score = st["best"]
        self.started = False
        self.finished = False
        self.loading = False

    @rx.event
    def choose(self, minutes: int):
        if minutes in graze_content.LENGTHS:
            self.minutes = minutes

    @rx.event
    def begin(self):
        """The button that starts it. The script watches for the click through
        its data attribute; this only moves the screen out of its menu state."""
        self.started = True
        self.finished = False
        self.gained_xp = 0
        self.just_earned = ""

    @rx.event
    def quit_early(self):
        """Stopping early is not a failure and is not logged — the session was
        for a set length, and a partial one is just a person changing their
        mind."""
        self.started = False
        self.finished = False

    @rx.event
    async def finish(self, form: dict):
        """The clock ran out. Called once, by the browser, with the totals."""
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")

        def num(key, default=0):
            try:
                return max(0, int(float(form.get(key) or default)))
            except (TypeError, ValueError):
                return default

        self.last_score = num("score")
        self.last_wave = max(1, num("wave", 1))
        self.last_runs = max(1, num("runs", 1))
        self.last_chain = max(1, num("chain", 1))
        # Never trust a length from the browser: it decides the XP.
        minutes = self.minutes if self.minutes in graze_content.LENGTHS else 15

        with db.get_session() as s:
            self.gained_xp = breaks.log(
                s, uid, "graze", minutes, score=self.last_score,
                detail=f"wave {self.last_wave}")
            new = achievements.award(s, uid)
            st = breaks.stats(s, uid, "graze")

        self.just_earned = new[0]["title"] if new else ""
        self.sessions = st["sessions"]
        self.total_minutes = st["minutes"]
        self.best_score = st["best"]
        self.closing = random.choice(graze_content.RESPAWN_LINES)
        self.started = False
        self.finished = True

    @rx.event
    def again(self):
        self.finished = False
        self.started = False

    @rx.event
    def dismiss_earned(self):
        self.just_earned = ""


# ====================================================================
# achievements_state
# ====================================================================

@dataclasses.dataclass
class BadgeRow:
    key: str
    title: str
    blurb: str
    icon: str
    xp: int
    cat: str
    cat_name: str
    reached: bool
    percent: int
    is_next: bool


class AchievementsState(FeatureState, rx.State):
    badges: list[BadgeRow] = []
    filter_cat: str = ""

    reached: int = 0
    total: int = 0
    xp: int = 0
    xp_total: int = 0
    percent: int = 0

    next_title: str = ""
    next_blurb: str = ""
    next_percent: int = 0
    next_icon: str = ""
    next_xp: int = 0

    @rx.var
    def cats(self) -> list[list[str]]:
        """[key, label] pairs — a list of lists because Reflex renders that
        more simply than a list of tuples."""
        return [[k, n] for k, n in ach_content.CATEGORIES]

    @rx.var(deps=["reached", "total"])
    def headline(self) -> str:
        if self.reached == 0:
            return 'Nothing earned yet. The first few take about a minute.'
        if self.reached == self.total:
            return "You've reached every checkpoint. Nice work."
        return f"{self.reached} of {self.total} reached."

    @rx.event
    async def load(self):
        uid = await self._user_id()
        if uid is None:
            return rx.redirect("/login")

        with db.get_session() as s:
            # Rings first: several checkpoints depend on how far along an
            # application is, and a stale ring would hide an earned badge.
            progress.recompute_all(s, uid)
            stats = achievements.gather(s, uid)
            achievements.award(s, uid, stats)

            board = achievements.board(s, uid, stats)
            t = achievements.totals(s, uid)
            upcoming = ach_content.next_up(stats, 1)

        nxt = upcoming[0] if upcoming else None
        self.badges = [
            BadgeRow(key=b.key, title=b.title, blurb=b.blurb, icon=b.icon,
                     xp=b.xp, cat=b.cat, cat_name=b.cat_name,
                     reached=b.reached, percent=b.percent,
                     is_next=bool(nxt and b.key == nxt["key"]))
            for b in board
            if not self.filter_cat or b.cat == self.filter_cat
        ]
        self.reached, self.total = t["reached"], t["total"]
        self.xp, self.xp_total = t["xp"], t["xp_total"]
        self.percent = t["percent"]

        if nxt:
            self.next_title = nxt["title"]
            self.next_blurb = nxt["blurb"]
            self.next_icon = nxt["icon"]
            self.next_xp = nxt["xp"]
            self.next_percent = ach_content.progress_to(nxt, stats)
        else:
            self.next_title = ""
            self.next_blurb = ""
            self.next_icon = ""
            self.next_xp = 0
            self.next_percent = 100

        self.loading = False

    @rx.event
    async def set_filter(self, cat: str):
        self.filter_cat = "" if self.filter_cat == cat else cat
        return AchievementsState.load
