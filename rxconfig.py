import os
from pathlib import Path

import reflex as rx
from reflex.plugins import RadixThemesPlugin
from reflex_base.plugins.sitemap import SitemapPlugin

Path(__file__).parent.joinpath("data").mkdir(exist_ok=True)
os.environ.setdefault("REFLEX_HOT_RELOAD_EXCLUDE_PATHS", "data")

_BASE = Path(os.environ.get("VG_BASE_DIR", "").strip() or Path(__file__).parent).resolve()
_BASE.joinpath("data").mkdir(parents=True, exist_ok=True)
# as_posix(), so a Windows path becomes sqlite:///C:/Users/... — backslashes
# in a URL are escape characters, not separators.
_DB_URL = f"sqlite:///{(_BASE / 'data' / 'veritagnosis.db').as_posix()}"

_origins = [o.strip() for o in os.environ.get("VG_ORIGIN", "").split(",") if o.strip()]
CORS_ORIGINS = _origins or [
    # Development: the Node dev server serves the page on 3000 and talks to
    # this backend on 8000, so the browser's origin is 3000.
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

BACKEND_HOST = os.environ.get("VG_HOST", "").strip() or "127.0.0.1"

config = rx.Config(
    app_name="veritagnosis",
    backend_host=BACKEND_HOST,
    db_url=os.environ.get("VG_DB_URL", _DB_URL),
    cors_allowed_origins=CORS_ORIGINS,
    show_built_with_reflex=False,
    plugins=[RadixThemesPlugin(), SitemapPlugin()],
)
