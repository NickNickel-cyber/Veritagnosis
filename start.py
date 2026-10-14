#!/usr/bin/env python3
"""
Veritagnosis — one command to run the whole app.

    python start.py

That is the entire install procedure. This script needs nothing but Python
itself; it builds its own private environment, installs the pinned
dependencies into it, creates the secret keys and the database on first run,
and starts the app. Running it again is safe and is the normal way to start
the app every day.

    python start.py            start the app
    python start.py --dev      start with hot reload (for editing the code)
    python start.py --reset    rebuild the web frontend from scratch
    python start.py --check    set everything up, verify it, and stop
    python start.py --test     run the test suite

Most people never type this. Double-clicking Veritagnosis.bat on Windows or
Veritagnosis.command on macOS runs exactly the same thing.

Why this file exists
--------------------
Nothing here is clever. It exists because the two ways this app has actually
broken were both environment problems rather than code problems:

  1. `reflex run` was typed in a terminal where the project's virtual
     environment was not active, so a *different* Python ran — one with a
     half-installed copy of Reflex — and the app died inside Reflex's own
     imports. Nothing in the traceback pointed at this project. This script
     removes the possibility: it always runs the app with the interpreter
     inside .venv, whatever interpreter was used to launch it.

  2. Dependencies drifted, because they were specified as ranges. They are
     pinned now, and this script verifies that the environment can actually
     import Reflex before trying to start, repairing it if it cannot.

So: if something is wrong with the environment, this tells you in one
sentence instead of forty lines of someone else's stack trace.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
MIN_PYTHON = (3, 11)

# Bumped whenever requirements change, so an existing .venv knows to reinstall.
STAMP = VENV / ".vg-deps-stamp"


# ---------------------------------------------------------------- presentation

def say(msg: str = "") -> None:
    print(msg, flush=True)


def step(n: int, total: int, msg: str) -> None:
    say(f"  [{n}/{total}] {msg}")


def die(msg: str, *fix: str) -> "NoReturn":  # noqa: F821
    say()
    say(f"  Stopped: {msg}")
    for line in fix:
        say(f"      {line}")
    say()
    # On Windows this is usually a double-clicked window; without the pause it
    # closes before the message can be read.
    if platform.system() == "Windows" and sys.stdout.isatty():
        try:
            input("  Press Enter to close. ")
        except (EOFError, KeyboardInterrupt):
            pass
    raise SystemExit(1)


# ---------------------------------------------------------------- environment

def venv_python() -> Path:
    """The interpreter inside .venv, which is the only one that runs the app."""
    if platform.system() == "Windows":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def ensure_launcher_executable() -> None:
    """Keep Veritagnosis.command double-clickable on macOS and Linux.

    macOS runs a .command file when it is double-clicked only if the execute
    bit is set; without it, Finder opens the file in TextEdit instead, which
    looks like the app is broken. Git records the bit, so a clone is fine — but
    a zip made on Windows, or one unpacked by a tool that drops permissions,
    arrives without it.

    Repairing it here means that once the app has started by any route, the
    double-click works from then on.
    """
    if platform.system() == "Windows":
        return
    launcher = ROOT / "Veritagnosis.command"
    try:
        if launcher.exists() and not os.access(launcher, os.X_OK):
            launcher.chmod(launcher.stat().st_mode | 0o111)
    except OSError:
        pass        # not worth failing a start over


def ensure_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        die(
            f"this app needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer, "
            f"and this is {platform.python_version()}.",
            "Install a current Python from https://www.python.org/downloads/",
            "On Windows, tick 'Add python.exe to PATH' in the installer.",
        )


def ensure_venv() -> None:
    """Create .venv if it is missing or broken."""
    if venv_python().exists():
        return
    if VENV.exists():
        # A directory that exists without an interpreter in it is a failed or
        # half-deleted environment, and pip will behave strangely against it.
        say("      (removing an incomplete .venv and starting again)")
        shutil.rmtree(VENV, ignore_errors=True)
    say("      first run: building a private environment, this is a one-off")
    try:
        venv.EnvBuilder(with_pip=True, clear=True).create(VENV)
    except Exception as e:  # noqa: BLE001
        die(f"could not create the environment in .venv ({e}).",
            "Check you have write permission in this folder.")


def deps_fingerprint() -> str:
    """Contents of the requirement files, so any edit forces a reinstall."""
    parts = []
    for name in ("requirements.txt", "requirements-dev.txt"):
        f = ROOT / name
        parts.append(f.read_text(encoding="utf-8") if f.exists() else "")
    return str(hash("".join(parts)))


def pip_install(*args: str) -> bool:
    cmd = [str(venv_python()), "-m", "pip", "install", "--disable-pip-version-check",
           "-q", *args]
    return subprocess.run(cmd, cwd=ROOT).returncode == 0


def reflex_imports() -> bool:
    """Can the environment actually import the app framework?

    This is the check that would have caught the startup crash. A package can
    be listed as installed and still be unimportable — an interrupted install,
    a partially upgraded plugin — and the only reliable test is to import it.
    """
    probe = "import reflex, reflex.app, reflex_components_lucide.icon"
    return subprocess.run(
        [str(venv_python()), "-c", probe],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


def ensure_deps(dev: bool) -> None:
    req = "requirements-dev.txt" if dev else "requirements.txt"
    want = deps_fingerprint() + ("+dev" if dev else "")
    have = STAMP.read_text(encoding="utf-8").strip() if STAMP.exists() else ""

    if have != want or not reflex_imports():
        say("      installing dependencies (a minute or two the first time)")
        if not pip_install("-r", req):
            die("installing dependencies failed — see the pip output above.",
                "Usually this is no internet connection, or a proxy blocking it.")

    # Verify, then repair, then give up with something actionable. Never start
    # the app against an environment that cannot import its own framework.
    if not reflex_imports():
        say("      the install looks incomplete — repairing it")
        pip_install("--force-reinstall", "--no-cache-dir", "-r", req)
        if not reflex_imports():
            die("the environment cannot import Reflex even after reinstalling.",
                "Delete the .venv folder and run this again:",
                "  Windows:  rmdir /s /q .venv",
                "  macOS:    rm -rf .venv",
                "If it still fails, the pinned versions in requirements.txt may",
                "not have builds for this Python — try Python 3.12.")

    STAMP.write_text(want, encoding="utf-8")


# ---------------------------------------------------------------- first-run data

def manage(*args: str) -> bool:
    return subprocess.run(
        [str(venv_python()), str(ROOT / "scripts" / "manage.py"), *args],
        cwd=ROOT,
    ).returncode == 0


def ensure_keys_and_db() -> None:
    if not (ROOT / ".env").exists():
        say("      creating your encryption keys in .env (stays on this machine)")
        if not manage("init-keys"):
            die("could not create .env.")
    if not (ROOT / "data" / "veritagnosis.db").exists():
        say("      creating the database")
        if not manage("init-db"):
            die("could not create the database.")


def clear_stale_state() -> None:
    """Reflex pickles each browser session's screen state into .states/.

    Those pickles describe the state classes as they were when written, so
    after the app's code changes they can describe a shape that no longer
    exists. They are a cache — accounts, essays and progress are all in the
    database — so the safe move is to drop them on every start.
    """
    states = ROOT / ".states"
    if states.is_dir():
        for f in states.glob("*.pkl"):
            try:
                f.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------- running

def run_env() -> dict:
    env = os.environ.copy()

    # Reflex builds the web frontend with Bun by default. Bun's process.env is
    # a special object missing .hasOwnProperty, and React Router calls exactly
    # that, so the build dies with "process.env.hasOwnProperty is not a
    # function". Where npm exists, use it. Where it does not, let Reflex use
    # its own bundled toolchain and say what to do if the build fails.
    if shutil.which("npm"):
        env["REFLEX_USE_NPM"] = "1"

    # react-router's dev server appends a flag to NODE_OPTIONS and relaunches
    # itself once. If the flag is already there it relaunches twice and throws
    # "the process has already been restarted". Start from empty.
    env["NODE_OPTIONS"] = ""

    # npm audit can hang for minutes on a slow connection.
    env["NPM_CONFIG_AUDIT"] = "false"
    return env


def start_app(dev: bool) -> int:
    cmd = [str(venv_python()), "-m", "reflex", "run"]
    if not dev:
        cmd += ["--env", "prod"]
    say()
    say("  ----------------------------------------------------------")
    say("   Veritagnosis is starting.")
    say()
    say("   Open:  http://localhost:3000")
    if not shutil.which("npm"):
        say()
        say("   Note: Node.js was not found, so Reflex will use its own")
        say("   bundled build tool. If the frontend build fails, install")
        say("   Node.js LTS from https://nodejs.org and run this again.")
    say()
    say("   Leave this window open. Press Ctrl+C to stop.")
    say("  ----------------------------------------------------------")
    say()
    try:
        return subprocess.run(cmd, cwd=ROOT, env=run_env()).returncode
    except KeyboardInterrupt:
        return 0


# ---------------------------------------------------------------- entry

def main() -> int:
    args = {a.lstrip("-").lower() for a in sys.argv[1:]}
    dev = "dev" in args
    want_tests = "test" in args or "tests" in args
    check_only = "check" in args

    say()
    say("  Veritagnosis")
    say()

    total = 4
    step(1, total, "checking Python")
    ensure_python_version()
    ensure_launcher_executable()

    step(2, total, "preparing the environment")
    ensure_venv()

    step(3, total, "checking dependencies")
    ensure_deps(dev=dev or want_tests or check_only)

    if "reset" in args:
        say("      clearing the web build so it is made fresh")
        shutil.rmtree(ROOT / ".web", ignore_errors=True)
        shutil.rmtree(ROOT / "reflex.lock", ignore_errors=True)

    step(4, total, "checking your keys and database")
    ensure_keys_and_db()
    clear_stale_state()

    if want_tests:
        say()
        return subprocess.run([str(venv_python()), "-m", "pytest", "-q"],
                              cwd=ROOT).returncode

    if check_only:
        say()
        say("  Everything is set up and the environment imports correctly.")
        say("  Start the app with:  python start.py")
        say()
        return 0

    return start_app(dev=dev)


if __name__ == "__main__":
    raise SystemExit(main())
