"""
What runs when your client double-clicks Veritagnosis.

This is the entry point PyInstaller packages (see build_exe.py). A packaged app
has to do four things the development launcher does not:

1. **Keep data outside itself.** A one-file executable unpacks into a temporary
   directory the operating system deletes on exit. Anything written relative to
   the code — the database, the keys — would vanish when the window closed, and
   the next launch would look like a fresh install. So before importing any of
   the app, VG_BASE_DIR is pointed at the folder the executable sits in.

2. **Serve the web page and the backend from one process.** There is no Node in
   the bundle and no second process. Reflex supports exactly this:
   REFLEX_MOUNT_FRONTEND_COMPILED_APP makes it mount the compiled frontend into
   its own ASGI app. That is used here rather than mounting static files by
   hand — the hand-rolled version worked for pages and silently broke every
   interaction, because the thing that has to be served is not just the files
   but Reflex's whole route table in the right order.

   One port serves both, so it must be the port the frontend was built to talk
   to (rxconfig.py's api_url).

3. **Run the app WITH its lifespan.** `app()` returns the real ASGI
   application: a wrapper whose lifespan starts Reflex's event processor.
   Serving the inner `app._api` instead starts a server that accepts websocket
   connections and then raises "Event processor is not initialized" on every
   event — the page renders, nothing responds, and nothing in the browser says
   why. That was this file's first version.

4. **Make its own keys and database, and open a browser**, because nobody is
   going to run a setup command or type a URL.
"""

from __future__ import annotations

import os
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


def home_dir() -> Path:
    """Where this install keeps its data. Beside the executable."""
    if frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# This block must run before anything from veritagnosis is imported: config.py
# reads VG_BASE_DIR at import time to decide where the database lives.
# ---------------------------------------------------------------------------
HOME = home_dir()
BUNDLE = bundle_dir()
os.environ.setdefault("VG_BASE_DIR", str(HOME))
(HOME / "data").mkdir(parents=True, exist_ok=True)

# The frontend was built expecting the backend at this port (rxconfig.py's
# api_url). Serving on any other port would load the page and then fail every
# interaction, which looks like the app is broken rather than busy.
PORT = 8000


def say(msg: str = "") -> None:
    print(msg, flush=True)


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
    """Copy the bundled college catalogue in on first run.

    Shipped as a separate seed file and copied rather than used in place,
    because the bundle is read-only and thrown away on exit.
    """
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
        input("  Press Enter to close. ")
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
            input("  Press Enter to close. ")
            return 1
    else:
        # In the bundle the files sit at <bundle>/web/build/client, matching
        # the layout Reflex expects under a web directory.
        pass
    os.environ["REFLEX_WEB_WORKDIR"] = str(web)

    # Reflex resolves several things relative to the CURRENT DIRECTORY, not to
    # where its code lives: rxconfig.py, the assets folder named in
    # App(stylesheets=...), and the .web directory. On a client's machine the
    # current directory is wherever they put the executable, and it contains
    # nothing but the executable — so compiling died on
    # "The stylesheet file .../assets/theme.css does not exist", and rxconfig.py
    # was never read at all (which silently dropped the Radix plugin config).
    #
    # Working from inside the bundle fixes all of those at once. Everything the
    # student's data touches is given an absolute path below, so moving the
    # working directory cannot move their essays into a temporary folder.
    if frozen():
        os.chdir(BUNDLE)

    # rxconfig.py sets db_url to the RELATIVE "sqlite:///data/veritagnosis.db",
    # and db.py prefers Reflex's db_url over its own path — so after the chdir
    # above the database would be created inside the bundle's temporary
    # directory and deleted on exit. This is the hook rxconfig.py already reads.
    os.environ.setdefault("VG_DB_URL",
                          f"sqlite:///{(HOME / 'data' / 'veritagnosis.db')}")

    # Not an environment variable. Reflex declares this one internal — its real
    # name is "__REFLEX_MOUNT_FRONTEND_COMPILED_APP" — so setting the obvious
    # name does nothing at all, silently, and the frontend simply is not
    # mounted: every page 404s while /ping answers fine. Reflex's own CLI sets
    # it through this same call.
    from reflex.config import environment
    environment.REFLEX_MOUNT_FRONTEND_COMPILED_APP.set(True)

    # Imported only now, so everything above is already in place.
    from veritagnosis import db
    db.init_db()

    from veritagnosis.veritagnosis import app

    # No explicit _compile() — app() does it. Calling both compiled the whole
    # app twice on every launch, which doubled a slow startup for nothing.
    #
    # app() — not app._api. The returned wrapper owns the lifespan that starts
    # the event processor; without it every interaction fails. See the note at
    # the top of this file.
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
