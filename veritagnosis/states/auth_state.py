"""
Signup, login, verification, and the logged-in user.

Two rules this file exists to honour:

  1. Passwords never enter State. Forms submit straight to an event handler and
     the value lives only in that handler's local scope. A password in a regular
     State var would be synchronised to the browser.
  2. The session token is a backend-only var (underscore) plus a LocalStorage
     var. Reflex does not sync underscore vars to the client, and the
     LocalStorage copy is the browser's own cookie-equivalent, not something the
     server echoes back into the page.
"""

from __future__ import annotations

import asyncio
import json

import reflex as rx
from sqlmodel import select

from veritagnosis import db, mailer
from veritagnosis.models import Essay, School, User
from veritagnosis import security as auth
from veritagnosis.ui import avatar as avatar_parts


class AuthState(rx.State):
    # Browser-held session token. This is the one value the client legitimately
    # keeps — it is the equivalent of a session cookie.
    token: str = rx.LocalStorage("", name="vg_session")

    # Everything below is display state, safe to sync.
    username: str = ""
    display_name: str = ""
    level: int = 1
    xp: int = 0
    xp_needed: int = 500
    streak: int = 0
    avatar_json: str = "{}"
    essays_left: int = 0
    schools_count: int = 0

    # Today's task, as chosen by services.apply.next_task from this student's
    # real schools and essays. Held as plain vars rather than computed, because
    # working it out reads several tables and that belongs in one deliberate
    # call on load, not in a @rx.var that re-runs on every render.
    task_title_v: str = "Loading your list"
    task_meta_v: str = ""
    task_route_v: str = "/home"

    # Which user the display vars above describe. A Reflex state outlives a
    # login — it belongs to the browser session — so without this stamp the
    # previous student's avatar and XP stay on screen after someone else signs
    # in. Checked every time a user is loaded.
    owner_id: int = 0

    error: str = ""
    busy: bool = False

    # Proof-of-life for the connection watchdog in motion.js.
    #
    # When the websocket to the Python side dies — the laptop slept, the wifi
    # dropped, the server restarted — the page looks completely normal and does
    # nothing at all. Buttons still light up, and no error appears anywhere.
    # That silent version of broken is what "if the app is open too long, it
    # breaks" actually was. Every few minutes the browser asks for this number
    # to go up; if it does not, the page knows the connection is gone and says
    # so instead of pretending to work.
    beat: int = 0

    # Signup is paced across three panels. All three live inside ONE form, so
    # the browser holds the values and the password is never assigned to a
    # State var — which would sync it to the client.
    step: int = 0
    STEPS: int = 3
    emailed: bool = False
    verified_just_now: bool = False

    # ---------------------------------------------------------- second factor
    #
    # What the browser is allowed to remember between the two steps.
    #
    # Previously this was the user id and the full email address, both in local
    # storage. That is a plain-text record of exactly who is signing in, sitting
    # on the disk of whatever machine they used — a shared library computer, a
    # sibling's laptop — long after they have gone. It was also trusted on the
    # way back in, so the verify step could be pointed at any account by editing
    # one value in the developer console.
    #
    # Now the browser holds one opaque handle. It is 256 random bits, it means
    # nothing without the server's row, it expires in ten minutes, and it says
    # nothing about whose login it belongs to. The masked address is rebuilt
    # from the server each time the page opens, so even that never persists.
    pending_challenge: str = rx.LocalStorage("", name="vg_challenge")
    masked_email: str = ""
    code: str = ""

    # Demo mode.
    #
    # With no mail server configured there is no way to receive a code, and an
    # app nobody can sign into is no use to someone evaluating it. So in that
    # one configuration the code is shown on screen.
    #
    # This is a real reduction in security and it is treated as one: it is
    # never a setting, only a consequence of having no mail set up; it is
    # announced in a banner on every screen that matters; and it is populated
    # ONLY when the mailer reports it is unconfigured. A send that was attempted
    # and failed leaves this empty, because that is a broken mail server rather
    # than an absent one, and leaking the code to the browser there would turn
    # an outage into a vulnerability.
    demo_code: str = ""

    # deps spelled out: the body calls a helper, so Reflex cannot infer them.
    @rx.var(deps=["avatar_json"])
    def avatar_svg(self) -> str:
        """The figure at the top-left of the home screen."""
        try:
            sel = json.loads(self.avatar_json or "{}")
        except (ValueError, TypeError):
            sel = {}
        return avatar_parts.render(sel, 112)

    @rx.var
    def xp_to_go(self) -> int:
        return max(0, self.xp_needed - self.xp)

    @rx.var(deps=["task_title_v", "task_meta_v", "task_route_v"])
    def task_title(self) -> str:
        return self._task[0]

    @rx.var(deps=["task_title_v", "task_meta_v", "task_route_v"])
    def task_meta(self) -> str:
        return self._task[1]

    @rx.var(deps=["task_title_v", "task_meta_v", "task_route_v"])
    def task_route(self) -> str:
        return self._task[2]

    @property
    def _task(self) -> tuple[str, str, str]:
        """Today's one task — read from this student's own rows.

        Deliberately one thing. The whole point of the screen is that a student
        opening it at 11pm sees a single next action, not a backlog.

        The work of choosing it is in services.apply.next_task, next to the
        deadline and milestone helpers it needs. These three vars are filled by
        load_home; the defaults below are what shows for the half-second before
        that returns, so they promise nothing.
        """
        return (self.task_title_v, self.task_meta_v, self.task_route_v)

    @rx.var
    def step_label(self) -> str:
        return ["Who you are", "How we reach you", "A little about you"][self.step]

    @rx.var
    def is_last_step(self) -> bool:
        return self.step == self.STEPS - 1

    @rx.var
    def logged_in(self) -> bool:
        return bool(self.username)

    @rx.var
    def xp_percent(self) -> int:
        return min(100, int(100 * self.xp / self.xp_needed)) if self.xp_needed else 0

    # ------------------------------------------------------------ signup
    @rx.event
    def next_step(self):
        """Advance one panel. Nothing is validated here on purpose — stopping
        someone mid-flow to scold them is exactly the pressure we're removing.
        Everything is checked once, on submit."""
        self.error = ""
        if self.step < self.STEPS - 1:
            self.step += 1

    @rx.event
    def prev_step(self):
        self.error = ""
        if self.step > 0:
            self.step -= 1

    @rx.event
    def reset_signup(self):
        self.step = 0
        self.error = ""

    @rx.event
    async def handle_signup(self, form: dict):
        """Receives the whole form at once. The password exists only inside this
        function — never as a State var, so it never reaches the browser."""
        self.error = ""
        self.busy = True
        yield
        email = (form.get("email") or "").strip()
        try:
            with db.get_session() as s:
                user = auth.register(
                    s,
                    form.get("username", ""),
                    form.get("password", ""),
                    email=email or None,
                    age=form.get("age") or None,
                    gender=form.get("gender") or None,
                )
                # The same two-step flow as a normal sign-in. Confirming the
                # address and completing the second factor are the same act, so
                # there is no separate "verify your email" state to get stuck in.
                handle, code = auth.begin_challenge(s, user)
                self.pending_challenge = handle
                self.masked_email = _mask(email)
        except auth.RegistrationError as e:
            self.busy = False
            self.error = str(e)
            self.step = 0 if ("sername" in str(e) or "assword" in str(e)) else 1
            return   # bare: this handler is an async generator
        except Exception as e:                      # noqa: BLE001
            # Anything unexpected (a storage problem, a bad key) must not throw
            # a stack trace at someone trying to make an account.
            self.busy = False
            self.error = ("Something went wrong saving your account. Close the "
                          "app, run it again, and try once more.")
            print(f"\n[veritagnosis] signup failed: {type(e).__name__}: {e}\n")
            return

        # SMTP blocks for a second or two; _send_code puts it off the event
        # loop so the UI does not freeze while Gmail answers.
        await self._send_code(email, code)

        self.busy = False
        yield rx.redirect("/verify")
    # ------------------------------------------------------------- login
    @rx.event
    async def handle_login(self, form: dict):
        """Step one of two. A correct password here does not sign anyone in.

        `auth.login` has no success return: it raises SecondFactorRequired and
        hands back a challenge. Anything else that comes out of it is a failure.
        """
        self.error = ""
        self.busy = True
        yield
        try:
            with db.get_session() as s:
                auth.login(s, form.get("username", ""), form.get("password", ""))
            # Unreachable: login never returns. If a future edit gives it a
            # success path, refuse to proceed rather than silently skipping the
            # second factor.
            self.busy = False
            self.error = "Sign-in could not be completed. Please try again."
            return
        except auth.SecondFactorRequired as e:
            self.pending_challenge = e.challenge
            self.masked_email = _mask(e.email)
            await self._send_code(e.email, e.code)
        except PermissionError as e:
            self.busy = False
            self.error = str(e)
            return
        except Exception as e:                      # noqa: BLE001
            self.busy = False
            self.error = ("Something went wrong signing you in. Close the app, "
                          "run it again, and try once more.")
            print(f"\n[veritagnosis] login failed: {type(e).__name__}: {e}\n")
            return
        self.busy = False
        yield rx.redirect("/verify")

    async def _send_code(self, email: str, code: str | None) -> None:
        """Mail the code, and say nothing about it anywhere else.

        The code is never stored on the state and never printed when the mail
        goes through — it is a second factor, and a second factor in a log file
        is not a second factor. The one exception is a send that fails: without
        the fallback the account would be unreachable, and the terminal belongs
        to whoever is running the app.
        """
        self.demo_code = ""
        if not code:
            self.emailed = False
            return
        configured = mailer.is_configured()
        try:
            # The lifetime is passed, not assumed: the mailer's own default is
            # 15 minutes and the challenge dies at 10, so leaving it out told
            # students the code was good for five minutes after it had expired.
            self.emailed = await asyncio.to_thread(
                mailer.send_verification_code, email, code,
                auth.CHALLENGE_TTL_MINUTES)
        except mailer.MailError as err:
            # Mail IS set up and the send failed. Do not put the code in the
            # browser — print it where only the operator can see it.
            self.emailed = False
            print(f"\n[veritagnosis] could not email the sign-in code ({err}).\n"
                  f"[veritagnosis] code for this attempt: {code}\n")
            return
        if not self.emailed and not configured:
            self.demo_code = code

    # ------------------------------------------------------ verification
    @rx.var
    def demo_mode(self) -> bool:
        """True when no mail server is configured, so codes appear on screen."""
        return not mailer.is_configured()

    @rx.event
    def set_code(self, value: str):
        self.code = "".join(c for c in value if c.isdigit())[:6]
        self.error = ""

    @rx.event
    def load_verify(self):
        """Runs when /verify opens.

        The masked address is fetched from the server against the handle rather
        than read out of browser storage, so a stale or forged handle shows
        nothing at all.
        """
        self.error = ""
        self.code = ""
        self.masked_email = ""
        if not self.pending_challenge:
            return
        with db.get_session() as s:
            email = auth.challenge_email(s, self.pending_challenge)
        if email:
            self.masked_email = _mask(email)
        else:
            self.pending_challenge = ""
            self.error = ("That sign-in request has expired. "
                          "Sign in again and we'll send a fresh code.")

    @rx.event
    def handle_verify(self):
        """Step two of two, and the only place a session is created."""
        if len(self.code) != 6:
            self.error = "Enter all six digits."
            return
        if not self.pending_challenge:
            self.error = ("We lost track of this sign-in. "
                          "Sign in again and we'll send a fresh code.")
            return
        try:
            with db.get_session() as s:
                token, user = auth.complete_login(s, self.pending_challenge,
                                                  self.code)
                self.token = token
                self._load_user(user)
        except PermissionError as e:
            self.code = ""
            self.error = str(e)
            return
        except Exception as e:                      # noqa: BLE001
            self.code = ""
            self.error = ("Something went wrong finishing your sign-in. "
                          "Try once more.")
            print(f"\n[veritagnosis] verify failed: {type(e).__name__}: {e}\n")
            return
        self.code = ""
        self.pending_challenge = ""
        self.masked_email = ""
        self.demo_code = ""
        self.verified_just_now = True
        return rx.redirect("/home")

    @rx.event
    async def resend_code(self):
        """A fresh code, and a fresh handle with it.

        Reusing the handle would carry the attempt counter across, which would
        turn "resend" into a way to reset your five guesses.
        """
        if not self.pending_challenge:
            self.error = "Sign in again and we'll send a fresh code."
            return
        with db.get_session() as s:
            fresh = auth.resend_code(s, self.pending_challenge)
        if fresh is None:
            self.pending_challenge = ""
            self.masked_email = ""
            self.error = ("That sign-in request has expired. "
                          "Sign in again and we'll send a fresh code.")
            return
        handle, code, email = fresh
        self.pending_challenge = handle
        self.masked_email = _mask(email)
        self.error = ""
        await self._send_code(email, code)

    # ------------------------------------------------------- home summary
    # Checkpoint numbers for the strip on the home screen. Loaded by their own
    # event rather than in _load_user, because working them out reads every
    # essay and scores it — worth doing once on the home screen, wasteful on
    # every single page.
    ach_reached: int = 0
    ach_total: int = 0
    ach_next: str = ""
    ach_next_icon: str = ""
    ach_next_pct: int = 0

    @rx.var(deps=["ach_reached", "ach_total"])
    def ach_line(self) -> str:
        if self.ach_total == 0:
            return ""
        if self.ach_reached == 0:
            return "No checkpoints yet — the first few are one click away."
        return f"{self.ach_reached} of {self.ach_total} checkpoints reached"

    @rx.event
    def load_home(self):
        """Refresh the rings and award anything earned since last time."""
        from veritagnosis.content import achievements as ach_content
        from veritagnosis.services import wellbeing as achievements, apply as progress

        with db.get_session() as s:
            user = auth.session_user(s, self.token)
            if user is None:
                return
            progress.recompute_all(s, user.id)
            task = progress.next_task(s, user.id)
            self.task_title_v = task.title
            self.task_meta_v = task.meta
            self.task_route_v = task.route
            stats = achievements.gather(s, user.id)
            achievements.award(s, user.id, stats)
            t = achievements.totals(s, user.id)
            upcoming = ach_content.next_up(stats, 1)
            # XP may have moved if something was just awarded.
            fresh = s.get(User, user.id)
            if fresh:
                self.xp = fresh.xp
                self.level = 1 + fresh.xp // 500
                self.xp_needed = 500 * self.level

        self.ach_reached, self.ach_total = t["reached"], t["total"]
        if upcoming:
            self.ach_next = upcoming[0]["title"]
            self.ach_next_icon = upcoming[0]["icon"]
            self.ach_next_pct = ach_content.progress_to(upcoming[0], stats)
        else:
            self.ach_next = ""
            self.ach_next_icon = "👑"
            self.ach_next_pct = 100

    @rx.event
    def heartbeat(self):
        """Answer the watchdog. Deliberately the cheapest possible handler —
        it touches no database and no session, because its only job is to prove
        that messages are still getting through."""
        self.beat = (self.beat + 1) % 1000000

    # ------------------------------------------------------------ session
    @rx.event
    def check_session(self):
        """Runs on_load for protected pages.

        `@require_login`-style page guards only redirect — the page source still
        ships. Anything private has to be fetched here, after the token is
        checked, and only then assigned to a var.
        """
        with db.get_session() as s:
            user = auth.session_user(s, self.token)
            if user is None:
                # No valid session: everything on screen belonged to whoever
                # was here last, so none of it may stay.
                self._clear_profile()
                return rx.redirect("/login")
            self._load_user(user)

    @rx.event
    async def sign_out(self):
        """End the session and leave nothing behind.

        Clearing the token is not enough on its own. Every screen keeps its own
        state object — the draft essay, the school board, the meditation
        streak, the avatar being edited — and those objects belong to the
        browser session, not to the login. Left alone they would still be
        holding this student's data when the next person signs in on the same
        computer, which is exactly the "it forgets whose account is whose"
        problem. So every one of them is emptied here, explicitly.
        """
        with db.get_session() as s:
            auth.logout(s, self.token)

        self.token = ""
        self.pending_challenge = ""
        self.masked_email = ""
        self._clear_profile()

        # Imported inside the function on purpose: these modules import this
        # one, so a module-level import would be circular.
        from veritagnosis.states.play_state import AchievementsState
        from veritagnosis.states.money_state import AidState
        from veritagnosis.states.play_state import AvatarState
        from veritagnosis.states.apply_state import EssayState
        from veritagnosis.states.play_state import GrazeState
        from veritagnosis.states.play_state import MeditationState
        from veritagnosis.states.profile_state import ProfileState
        from veritagnosis.states.apply_state import RecsState
        from veritagnosis.states.apply_state import SchoolsState

        for cls in (AchievementsState, AidState, AvatarState, EssayState,
                    GrazeState, MeditationState, ProfileState, RecsState,
                    SchoolsState):
            (await self.get_state(cls)).reset()

        return rx.redirect("/")

    def _clear_profile(self) -> None:
        """Put every display var back to its signed-out default."""
        self.username = ""
        self.display_name = ""
        self.level = 1
        self.xp = 0
        self.xp_needed = 500
        self.streak = 0
        self.avatar_json = "{}"
        self.essays_left = 1
        self.schools_count = 0
        self.owner_id = 0
        self.error = ""

    def _load_user(self, user) -> None:
        # A different person than the state currently describes: drop the old
        # values first so nothing from the previous account can survive a field
        # that happens not to be overwritten below.
        if self.owner_id and self.owner_id != user.id:
            self._clear_profile()
        self.owner_id = user.id

        self.username = user.username
        self.display_name = user.username
        self.xp = user.xp
        self.level = 1 + user.xp // 500
        self.xp_needed = 500 * self.level
        self.streak = user.streak_days
        self.avatar_json = user.avatar or "{}"
        # Counts that decide today's task. Cheap queries, one per load.
        with db.get_session() as s:
            self.essays_left = len([e for e in s.exec(
                select(Essay).where(Essay.user_id == user.id)).all() if not e.done])
            self.schools_count = len(s.exec(
                select(School).where(School.user_id == user.id)).all())

    @rx.var
    def avatar_selection(self) -> dict:
        try:
            return json.loads(self.avatar_json)
        except (ValueError, TypeError):
            return {}


def _mask(email: str) -> str:
    """t***@gmail.com — enough for the student to recognise, not enough to
    hand a shoulder-surfer the address."""
    if "@" not in email:
        return "your email"
    name, domain = email.split("@", 1)
    return f"{name[:1]}{'*' * max(3, len(name) - 1)}@{domain}"
