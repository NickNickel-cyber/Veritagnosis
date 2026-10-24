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

# Where the database file actually is.
#
# This used to read "sqlite:///data/veritagnosis.db". SQLAlchemy resolves a
# relative SQLite path against the PROCESS WORKING DIRECTORY, not against this
# file — so the app did not have one database, it had one per folder it was
# ever started from. Double-clicking the executable, running it from a
# shortcut and running it from a terminal could each open a different file,
# and every one of them looked like a brand-new install: no account, no
# essays, no checkpoints. Nothing was lost; the app was simply looking
# somewhere else.
#
# Anchored instead to VG_BASE_DIR when it is set — launch.py sets it to the
# folder the executable sits in, because inside a one-file bundle this module
# lives in a temporary directory the operating system deletes on exit — and
# otherwise to this file's own folder. Absolute either way, so the working
# directory stops mattering.
_BASE = Path(os.environ.get("VG_BASE_DIR", "").strip() or Path(__file__).parent).resolve()
_BASE.joinpath("data").mkdir(parents=True, exist_ok=True)
# as_posix(), so a Windows path becomes sqlite:///C:/Users/... — backslashes
# in a URL are escape characters, not separators.
_DB_URL = f"sqlite:///{(_BASE / 'data' / 'veritagnosis.db').as_posix()}"

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
    # Development: the Node dev server serves the page on 3000 and talks to
    # this backend on 8000, so the browser's origin is 3000.
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # Packaged (launch.py): one process serves BOTH the page and the backend on
    # 8000, so the origin is 8000. Without these the page loads and every
    # interaction fails — the websocket handshake comes back 403 and the app
    # looks frozen rather than blocked, which is the worst way for this to go
    # wrong. Still localhost-only, so this is not a loosening.
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Which network interface the server listens on.
#
# Reflex listens on 0.0.0.0 unless told otherwise, which means every device on
# the same Wi-Fi can reach the app running on a student's laptop: a school or
# library network full of strangers, talking to a server that holds essays and
# GPAs. Nobody running it from a downloaded copy needs that, so the default is
# 127.0.0.1 — this computer only. The page opens exactly as before, at
# http://localhost:3000.
#
# A real deployment (the Dockerfile, a hosting service) has to listen on every
# interface and sets VG_HOST=0.0.0.0 itself, together with VG_ORIGIN.
BACKEND_HOST = os.environ.get("VG_HOST", "").strip() or "127.0.0.1"

config = rx.Config(
    app_name="veritagnosis",
    backend_host=BACKEND_HOST,
    db_url=os.environ.get("VG_DB_URL", _DB_URL),
    cors_allowed_origins=CORS_ORIGINS,
    # Declared explicitly: implicit Radix enablement is deprecated in 0.9 and
    # removed in 1.0. rx.heading / rx.hstack / rx.link are Radix components.
    # The sticky "Built with Reflex" badge overlaps the scene artwork.
    show_built_with_reflex=False,
    plugins=[RadixThemesPlugin(), SitemapPlugin()],
)
