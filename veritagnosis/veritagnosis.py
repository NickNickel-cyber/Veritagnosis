
from __future__ import annotations

import logging

import reflex as rx

from veritagnosis import db
from veritagnosis.security import security_headers
from veritagnosis.pages.home import achievements_page
from veritagnosis.pages.aid import aid_page
from veritagnosis.pages.apply import applications_page
from veritagnosis.pages.home import avatar_page
from veritagnosis.pages.apply import essays_page
from veritagnosis.pages.play import graze_page
from veritagnosis.pages.home import home
from veritagnosis.pages.auth import login
from veritagnosis.pages.play import meditation_page
from veritagnosis.pages.profile import profile_page
from veritagnosis.pages.apply import recommendations_page
from veritagnosis.pages.auth import settings_page
from veritagnosis.pages.auth import signup
from veritagnosis.pages.auth import splash
from veritagnosis.pages.auth import verify
from veritagnosis.states.play_state import AchievementsState
from veritagnosis.states.money_state import AidState
from veritagnosis.states.auth_state import AuthState


class _QuietClosedTabs(logging.Filter):

    def filter(self, record: logging.LogRecord) -> bool:
        return "send delta to disconnected client" not in record.getMessage()


logging.getLogger("reflex.app").addFilter(_QuietClosedTabs())
from veritagnosis.states.play_state import AvatarState
from veritagnosis.states.apply_state import EssayState
from veritagnosis.states.play_state import GrazeState
from veritagnosis.states.play_state import MeditationState
from veritagnosis.states.profile_state import ProfileState
from veritagnosis.states.apply_state import RecsState
from veritagnosis.states.apply_state import SchoolsState
from veritagnosis.ui.theme import FONTS

db.init_db()

app = rx.App(stylesheets=["/theme.css", *FONTS],
             head_components=[
                 rx.el.link(rel="icon", type="image/png", href="/favicon.png"),
                 rx.el.link(rel="apple-touch-icon", href="/logo.png"),
             ],
             api_transformer=security_headers)

app.add_page(splash, route="/", title="Veritagnosis")
app.add_page(signup, route="/signup", title="Create your account · Veritagnosis")
app.add_page(login, route="/login", title="Log in · Veritagnosis")
app.add_page(verify, route="/verify", title="Verify your email · Veritagnosis",
             on_load=AuthState.load_verify)

app.add_page(home, route="/home", title="Home · Veritagnosis",
             on_load=[AuthState.check_session, AuthState.load_home])

for page, route, title, loader in [
    (avatar_page, "/avatar", "Your avatar", AvatarState.load),
    (profile_page, "/profile", "Your profile", ProfileState.load),
    (essays_page, "/essays", "Essay coach", EssayState.load),
    (meditation_page, "/meditation", "Meditation", MeditationState.load),
    (recommendations_page, "/recommendations", "Recommendations", RecsState.load),
    (applications_page, "/applications", "Application progress", SchoolsState.load),
    (achievements_page, "/achievements", "Checkpoints", AchievementsState.load),
    (aid_page, "/aid", "Paying for it", AidState.load),
    (graze_page, "/graze", "Graze", GrazeState.load),
    (settings_page, "/settings", "Settings", AuthState.check_session),
]:
    app.add_page(page, route=route, title=f"{title} · Veritagnosis",
                 on_load=[AuthState.check_session, loader])
