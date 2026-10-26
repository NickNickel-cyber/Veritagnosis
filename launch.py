
from __future__ import annotations

import os
import platform
import shutil
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def frozen() -> bool:
    return getattr(sys, "frozen", False)


def bundle_dir() -> Path:
    """Where the packaged read-only files live."""
    if frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def _beside_the_app() -> Path:
    exe = Path(sys.executable).resolve()
    if not frozen():
        return Path(__file__).resolve().parent
    parts = exe.parts
    if ".app" in " ".join(parts) and len(parts) >= 4:
        for i in range(len(parts) - 1, 1, -1):
            if parts[i].endswith(".app"):
                return Path(*parts[:i])
    return exe.parent


def _user_data_dir() -> Path:
    """The per-user location each platform expects an app to write to."""
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        return Path(base) / "Veritagnosis"
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Veritagnosis"
    return Path(os.environ.get("XDG_DATA_HOME",
                               Path.home() / ".local" / "share")) / "veritagnosis"


def home_dir() -> Path:
    beside = _beside_the_app()
    try:
        beside.mkdir(parents=True, exist_ok=True)
        probe = beside / ".vg-write-test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return beside
    except OSError:
        fallback = _user_data_dir()
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


# This block must run before anything from veritagnosis is imported: config.py
# reads VG_BASE_DIR at import time to decide where the database lives.
HOME = home_dir()
BUNDLE = bundle_dir()
os.environ.setdefault("VG_BASE_DIR", str(HOME))
(HOME / "data").mkdir(parents=True, exist_ok=True)

PORT = 8000


_LOG: Path | None = None


def _log_path() -> "Path | None":
    global _LOG
    if _LOG is None:
        try:
            _LOG = HOME / "veritagnosis.log"
            _LOG.write_text("", encoding="utf-8")
        except OSError:
            _LOG = Path(os.devnull)
    return _LOG


def say(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except Exception:                                   # noqa: BLE001
        pass            # no console (a windowed .app); the log still has it
    try:
        with _log_path().open("a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except OSError:
        pass


def has_console() -> bool:
    """False in a windowed macOS .app, where input() would raise."""
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:                                   # noqa: BLE001
        return False


def pause(prompt: str = "  Press Enter to close. ") -> None:
    """Hold the window open — but only when there is a window."""
    if not has_console():
        return
    try:
        input(prompt)
    except (EOFError, KeyboardInterrupt):
        pass


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def ensure_env() -> None:
    """Keys on first run. Generated here, kept beside the executable."""
    env = HOME / ".env"
    if env.exists():
        return
    import secrets
    say("  First run — creating your encryption keys.")
    env.write_text(
        "# Created automatically on first run. Keep this file.\n"
        "# Deleting it makes existing essays and profiles unreadable.\n"
        f"VG_FIELD_KEY={secrets.token_urlsafe(32)}\n"
        f"VG_INDEX_KEY={secrets.token_urlsafe(32)}\n"
        "\n# Email (optional). Without these, sign-in codes appear on screen.\n"
        "# VG_SMTP_USER=\n"
        "# VG_SMTP_PASSWORD=\n"
        "VG_MAIL_FROM_NAME=Veritagnosis\n",
        encoding="utf-8",
    )
    try:
        os.chmod(env, 0o600)
    except OSError:
        pass


def ensure_colleges() -> None:
    seed = BUNDLE / "data" / "colleges.seed.db"
    target = HOME / "data" / "veritagnosis.db"
    if not seed.exists() or target.exists():
        return
    try:
        shutil.copy2(seed, target)
        say("  Loaded the college catalogue.")
    except OSError:
        pass        # not fatal: the app works with the curated colleges


def open_browser_when_ready(url: str) -> None:
    def wait():
        for _ in range(120):
            if not port_free(PORT):      # something is listening: that is us
                break
            time.sleep(0.25)
        try:
            webbrowser.open(url)
        except Exception:                # noqa: BLE001
            pass
    threading.Thread(target=wait, daemon=True).start()


def main() -> int:
    url = f"http://localhost:{PORT}"
    say()
    say("  Veritagnosis")
    say()

    if not port_free(PORT):
        say(f"  Port {PORT} is already in use on this computer.")
        say()
        say("  Veritagnosis needs that port. Another copy may already be")
        say(f"  running — try opening {url} first.")
        say("  Otherwise close whatever is using it and run this again.")
        say()
        pause()
        return 1

    ensure_env()
    ensure_colleges()

    # Point Reflex at the bundled frontend and tell it to serve it itself.
    # Both must be set before the app is imported.
    web = BUNDLE / "web"
    if not (web / "build" / "client" / "index.html").exists():
        # Not packaged: use wherever `reflex export` put it. Lets this file be
        # run directly to test the packaged behaviour without a build.
        local = Path(__file__).resolve().parent / ".web"
        if (local / "build" / "client" / "index.html").exists():
            web = local
        else:
            say(f"  No compiled frontend found at {web}.")
            say("  Run:  python build_exe.py   (or reflex export --frontend-only)")
            pause()
            return 1
    else:
        # In the bundle the files sit at <bundle>/web/build/client, matching
        # the layout Reflex expects under a web directory.
        pass
    os.environ["REFLEX_WEB_WORKDIR"] = str(web)

    if frozen():
        os.chdir(BUNDLE)

    os.environ.setdefault("VG_DB_URL",
                          f"sqlite:///{(HOME / 'data' / 'veritagnosis.db')}")

    from reflex.config import environment
    environment.REFLEX_MOUNT_FRONTEND_COMPILED_APP.set(True)

    # Imported only now, so everything above is already in place.
    from veritagnosis import db
    db.init_db()

    from veritagnosis.veritagnosis import app

    asgi = app()

    say("  ----------------------------------------------------------")
    say(f"   Open:  {url}")
    say()
    say("   Your work is saved in the 'data' folder next to this")
    say("   program. Keep them together.")
    say()
    say("   Leave this window open while you use the app.")
    say("   Closing it stops the app.")
    say("  ----------------------------------------------------------")
    say()

    open_browser_when_ready(url)

    import uvicorn
    try:
        uvicorn.run(asgi, host="127.0.0.1", port=PORT, log_level="warning")
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
