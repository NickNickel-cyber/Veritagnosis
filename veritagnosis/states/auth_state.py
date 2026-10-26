
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

    task_title_v: str = 'Loading…'
    task_meta_v: str = ""
    task_route_v: str = "/home"

    owner_id: int = 0

    error: str = ""
    busy: bool = False

    beat: int = 0

    step: int = 0
    STEPS: int = 3
    emailed: bool = False
    verified_just_now: bool = False

    pending_challenge: str = rx.LocalStorage("", name="vg_challenge")
    masked_email: str = ""
    code: str = ""

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

    @rx.event
    def next_step(self):
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
            self.error = (('Something went wrong creating your account. Restart the app and try '
                           'again.'))
            print(f"\n[veritagnosis] signup failed: {type(e).__name__}: {e}\n")
            return

        # SMTP blocks for a second or two; _send_code puts it off the event
        # loop so the UI does not freeze while Gmail answers.
        await self._send_code(email, code)

        self.busy = False
        yield rx.redirect("/verify")
    @rx.event
    async def handle_login(self, form: dict):
        self.error = ""
        self.busy = True
        yield
        try:
            with db.get_session() as s:
                auth.login(s, form.get("username", ""), form.get("password", ""))
            self.busy = False
            self.error = "We couldn't sign you in. Please try again."
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
            self.error = ('Something went wrong signing you in. Restart the app and try again.')
            print(f"\n[veritagnosis] login failed: {type(e).__name__}: {e}\n")
            return
        self.busy = False
        yield rx.redirect("/verify")

    async def _send_code(self, email: str, code: str | None) -> None:
        self.demo_code = ""
        if not code:
            self.emailed = False
            return
        configured = mailer.is_configured()
        try:
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
            self.error = ("That code has expired. Sign in again and we'll send you a new one.")

    @rx.event
    def handle_verify(self):
        """Step two of two, and the only place a session is created."""
        if len(self.code) != 6:
            self.error = "Enter all six digits."
            return
        if not self.pending_challenge:
            self.error = ("This sign-in timed out. Sign in again and we'll send you a new code.")
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
            self.error = ('Something went wrong finishing your sign-in. Please try again.')
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
        if not self.pending_challenge:
            self.error = "Sign in again and we'll send you a new code."
            return
        with db.get_session() as s:
            fresh = auth.resend_code(s, self.pending_challenge)
        if fresh is None:
            self.pending_challenge = ""
            self.masked_email = ""
            self.error = ("That code has expired. Sign in again and we'll send you a new one.")
            return
        handle, code, email = fresh
        self.pending_challenge = handle
        self.masked_email = _mask(email)
        self.error = ""
        await self._send_code(email, code)

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
            return 'No checkpoints yet. The first few take about a minute.'
        return f"{self.ach_reached} of {self.ach_total} checkpoints reached"

    hour: int = -1

    @rx.event
    def set_hour(self, value):
        try:
            h = int(value)
        except (TypeError, ValueError):
            return
        if 0 <= h <= 23:
            self.hour = h

    @rx.var(deps=["hour"])
    def greeting(self) -> str:
        return greeting_for(self.hour)

    @rx.var(deps=["display_name"])
    def greet_name(self) -> str:
        """The name as it is said out loud. "nick" becomes "Nick"; anything
        with digits or punctuation ("sri_2027") is left exactly as chosen."""
        n = (self.display_name or "").strip()
        if n.isalpha() and n[:1].islower():
            return n[:1].upper() + n[1:]
        return n

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
        self.beat = (self.beat + 1) % 1000000

    @rx.event
    def check_session(self):
        with db.get_session() as s:
            user = auth.session_user(s, self.token)
            if user is None:
                # No valid session: everything on screen belonged to whoever
                # was here last, so none of it may stay.
                self._clear_profile()
                return rx.redirect("/login")
            self._load_user(user)

    async def _forget_everything(self) -> None:
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

    @rx.event
    async def sign_out(self):
        """End the session and leave nothing behind."""
        with db.get_session() as s:
            auth.logout(s, self.token)
        await self._forget_everything()
        return rx.redirect("/")

    confirm_delete: bool = False
    delete_error: str = ""

    @rx.event
    def start_delete(self):
        self.confirm_delete = True
        self.delete_error = ""

    @rx.event
    def cancel_delete(self):
        self.confirm_delete = False
        self.delete_error = ""

    @rx.event
    async def delete_account(self, form: dict):
        """Check the password, then delete the account and everything in it."""
        self.delete_error = ""
        password = form.get("password", "")
        if not password:
            self.delete_error = "Type your password to confirm."
            return
        with db.get_session() as s:
            user = auth.session_user(s, self.token)
            if user is None:
                self.delete_error = ""
                return rx.redirect("/login")
            try:
                auth.delete_account(s, user, password)
            except PermissionError as e:
                self.delete_error = str(e)
                return
            except Exception as e:                      # noqa: BLE001
                self.delete_error = ("We couldn't delete your account. Nothing was changed.")
                print(f"\n[veritagnosis] delete failed: {type(e).__name__}: {e}\n")
                return
        self.confirm_delete = False
        await self._forget_everything()
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


# The browser's local hour, as a JavaScript expression compiled into the page.
BROWSER_HOUR = rx.Var(_js_expr="(new Date()).getHours()", _var_type=int)


def greeting_for(hour: int) -> str:
    if not 0 <= hour <= 23:
        return "Hello"
    if 5 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 17:
        return "Good afternoon"
    return "Good evening"


def _mask(email: str) -> str:
    """t***@gmail.com — enough for the student to recognise, not enough to
    hand a shoulder-surfer the address."""
    if "@" not in email:
        return "your email"
    name, domain = email.split("@", 1)
    return f"{name[:1]}{'*' * max(3, len(name) - 1)}@{domain}"
