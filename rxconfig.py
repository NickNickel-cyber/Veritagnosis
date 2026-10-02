import os
from pathlib import Path

import reflex as rx
from reflex.plugins import RadixThemesPlugin
from reflex_base.plugins.sitemap import SitemapPlugin

# Keep the dev server's file watcher out of data/.
#
# In development Reflex watches every top-level directory that is not hidden,
# and data/ holds the SQLite file. SQLite rewrites its -wal and -shm sidecars
# whenever the backend opens a connection, so the sequence was: backend starts,
# opens the database, touches a watched file, the watcher fires, the backend
# reloads, and it opens the database again. Measured here it restarted about
# thirty times a minute and never stayed up long enough to hold a websocket
# open, so every page rendered but nothing that needed state worked at all.
#
# The path is deliberately relative. This variable is split on ":", so an
# absolute Windows path would break apart at the drive letter and exclude
# nothing. Reflex resolves it against the working directory, which is this
# directory, because that is where rxconfig.py must be run from.
#
# setdefault, not assignment, so an explicit value in the environment wins.
Path(__file__).parent.joinpath("data").mkdir(exist_ok=True)
os.environ.setdefault("REFLEX_HOT_RELOAD_EXCLUDE_PATHS", "data")

# Which origins may talk to the backend.
#
# Reflex defaults this to ("*",), which is fine on a laptop and wrong the
# moment the app is reachable from the internet: it lets any page anywhere
# open a websocket to this backend. In production set VG_ORIGIN to the real
# origin, e.g. VG_ORIGIN=https://veritagnosis.example.com — several may be
# given, comma-separated.
#
# The localhost defaults are only used when VG_ORIGIN is unset, which is the
# development case. There is deliberately no "*" fallback: a missing variable
# in production should break the deploy loudly, not silently open it up.
_origins = [o.strip() for o in os.environ.get("VG_ORIGIN", "").split(",") if o.strip()]
CORS_ORIGINS = _origins or [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

config = rx.Config(
    app_name="veritagnosis",
    db_url=os.environ.get("VG_DB_URL", "sqlite:///data/veritagnosis.db"),
    cors_allowed_origins=CORS_ORIGINS,
    # Declared explicitly: implicit Radix enablement is deprecated in 0.9 and
    # removed in 1.0. rx.heading / rx.hstack / rx.link are Radix components.
    # The sticky "Built with Reflex" badge overlaps the scene artwork.
    show_built_with_reflex=False,
    plugins=[RadixThemesPlugin(), SitemapPlugin()],
)
