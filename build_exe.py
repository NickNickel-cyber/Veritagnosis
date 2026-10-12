#!/usr/bin/env python3
"""
Build Veritagnosis into a single file your client double-clicks.

    python build_exe.py

You run this once, on Windows. It produces:

    dist/Veritagnosis.exe

That is the whole handover. Your client double-clicks it. No Python, no
installing packages, no terminal, no downloads — the exe contains the
interpreter, every dependency, the compiled web frontend and the college data.
First launch creates their database and keys next to the exe and opens their
browser.

Why this is a build step and not something the client runs
----------------------------------------------------------
PyInstaller bundles the interpreter it is run by, for the platform it is run
on. It cannot cross-compile: a Windows .exe has to be built on Windows. So the
one machine that has to run a build is yours, once per release.

What it does, in order
----------------------
1. Makes sure the project's own environment exists and is complete (reuses
   start.py, so there is one definition of that).
2. Compiles the web frontend with `reflex export --frontend-only`. This is the
   part that needs Node, and it happens HERE so the client never does.
3. Runs PyInstaller over launch.py with the frontend, the assets and the
   college catalogue added as data.

Caveats worth knowing
---------------------
* The exe is large — 150-250MB. That is a whole Python interpreter plus the
  built frontend, and there is no way around it.
* Windows SmartScreen will warn on an unsigned exe the first time ("unknown
  publisher"). Your client clicks "More info" then "Run anyway", or you buy a
  code-signing certificate. Nothing in the build can avoid that; it is what
  signing is for.
* Antivirus occasionally flags PyInstaller output. If that happens, build with
  `--onedir` instead (set ONEDIR below) — a folder with an exe in it, which is
  less often misread than a single self-extracting file.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "Veritagnosis"

# A single self-contained file. Set to True if antivirus objects — see above.
ONEDIR = False


def say(msg: str = "") -> None:
    print(msg, flush=True)


def die(msg: str, *fix: str) -> "NoReturn":            # noqa: F821
    say()
    say(f"  Stopped: {msg}")
    for line in fix:
        say(f"      {line}")
    say()
    raise SystemExit(1)


def venv_python() -> Path:
    if platform.system() == "Windows":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def run(cmd: list[str], **kw) -> int:
    return subprocess.run(cmd, cwd=ROOT, **kw).returncode


def main() -> int:
    say()
    say(f"  Building {NAME}")
    say()

    if platform.system() != "Windows":
        say("  Note: you are not on Windows, so this will produce an")
        say(f"  executable for {platform.system()}, not a .exe. PyInstaller")
        say("  cannot cross-compile — build the Windows version on Windows.")
        say()

    # ---- 1. the environment ------------------------------------------
    say("  [1/4] environment")
    if run([sys.executable, "start.py", "--check"]) != 0:
        die("the project environment is not ready.",
            "Run `python start.py --check` on its own to see why.")

    py = venv_python()
    if not py.exists():
        die("no interpreter in .venv after setup.")

    say("  [2/4] build tools")
    if run([str(py), "-m", "pip", "install", "-q", "pyinstaller>=6.0"]) != 0:
        die("could not install PyInstaller.")

    # ---- 2. the frontend ---------------------------------------------
    # This is the step that needs Node, and the whole reason the client does
    # not: the compiled frontend is baked into the exe.
    say("  [3/4] compiling the web frontend (a few minutes)")
    env = dict(os.environ)
    if shutil.which("npm"):
        env["REFLEX_USE_NPM"] = "1"
    env["NODE_OPTIONS"] = ""
    env["NPM_CONFIG_AUDIT"] = "false"
    # config.py refuses to import without keys; these exist only for the
    # export and touch no real data.
    env.setdefault("VG_FIELD_KEY", "build-only-key-not-used-at-runtime-0001")
    env.setdefault("VG_INDEX_KEY", "build-only-key-not-used-at-runtime-0002")
    if subprocess.run([str(py), "-m", "reflex", "export", "--frontend-only",
                       "--no-zip"], cwd=ROOT, env=env).returncode != 0:
        die("the frontend build failed.",
            "Install Node.js LTS from https://nodejs.org and try again.")

    frontend = ROOT / ".web" / "build" / "client"
    if not (frontend / "index.html").exists():
        die(f"no frontend output at {frontend}.")

    # ---- 3. package ---------------------------------------------------
    say("  [4/4] packaging")
    sep = ";" if platform.system() == "Windows" else ":"
    args = [
        str(py), "-m", "PyInstaller", "--noconfirm", "--clean",
        "--name", NAME,
        "--onedir" if ONEDIR else "--onefile",
        # A console window is kept on purpose. It is where the sign-in code
        # appears if email is not configured, and where a startup error is
        # readable instead of the window vanishing.
        "--console",
        # Laid out as <bundle>/web/build/client, which is what Reflex expects
        # under a web directory — launch.py points REFLEX_WEB_WORKDIR at it.
        f"--add-data={frontend}{sep}web/build/client",
        f"--add-data={ROOT / 'assets'}{sep}assets",
        # rxconfig.py is read from the working directory at import time, so it
        # has to be inside the bundle (launch.py chdir's there). Without it
        # Reflex falls back to defaults and the CORS origins, db_url hook and
        # Radix plugin configuration are all silently lost.
        f"--add-data={ROOT / 'rxconfig.py'}{sep}.",
        # Reflex and SQLModel find plenty at runtime that a static scan misses.
        "--collect-all", "reflex",
        "--collect-all", "reflex_base",
        "--collect-all", "reflex_components_core",
        "--collect-all", "reflex_components_radix",
        "--collect-all", "reflex_components_lucide",
        "--collect-all", "sqlmodel",
        "--collect-all", "sqlalchemy",
        "--hidden-import", "veritagnosis.veritagnosis",
        "--hidden-import", "argon2",
        "--hidden-import", "cryptography",
    ]
    icon = ROOT / "assets" / "icon.ico"
    if icon.exists():
        args.append(f"--icon={icon}")

    # The curated catalogue is Python and comes along automatically; an
    # imported Scorecard database does not, so it is bundled when present.
    seed = ROOT / "data" / "colleges.seed.db"
    if seed.exists():
        args.append(f"--add-data={seed}{sep}data")
        say(f"      including the college catalogue ({seed.stat().st_size // 1048576}MB)")
    else:
        say("      no college catalogue found — the exe will ship with the")
        say("      curated colleges only. See README: import-colleges, then")
        say("      `python scripts/manage.py seed-colleges` to bundle it.")

    args.append(str(ROOT / "launch.py"))
    if run(args) != 0:
        die("PyInstaller failed — see its output above.")

    out = ROOT / "dist" / (NAME if ONEDIR else
                           (NAME + (".exe" if platform.system() == "Windows" else "")))
    say()
    say("  ----------------------------------------------------------")
    say(f"   Done:  {out}")
    say()
    say("   Give that to your client. They double-click it; nothing")
    say("   else is needed on their machine.")
    say()
    say("   First run on an unsigned exe shows a Windows SmartScreen")
    say("   warning — 'More info' then 'Run anyway'.")
    say("  ----------------------------------------------------------")
    say()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
