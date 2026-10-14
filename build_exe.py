#!/usr/bin/env python3
"""
Build Veritagnosis into one file your client double-clicks.

    python build_exe.py

Produces, depending on the machine you run it on:

    Windows   dist/Veritagnosis.exe      one file, double-click it
    macOS     dist/Veritagnosis.app      a normal Mac app, double-click it
    Linux     dist/Veritagnosis          one file, run it

The client needs nothing: no Python, no installing packages, no terminal. The
result contains the interpreter, every dependency, the compiled web page and
the college data. First launch creates their database and keys and opens their
browser.

Why there is no single file for both Windows and macOS
-----------------------------------------------------
There cannot be. A Windows executable is PE format and a macOS executable is
Mach-O; no file is both. PyInstaller also bundles the interpreter it is run by,
for the platform it is run on, and cannot cross-compile — so each platform's
build must happen on that platform.

You do not need a Mac for the Mac build. .github/workflows/build.yml runs this
script on GitHub's own Windows and macOS runners and attaches both results to
a release. Pushing a tag is the whole job.

Caveats worth knowing
---------------------
* The result is large (40-250MB) — a whole Python interpreter plus the frontend.
* **Windows** warns on an unsigned exe the first time ("unknown publisher"):
  More info -> Run anyway.
* **macOS is stricter.** An unsigned, un-notarised app downloaded from the
  internet is refused by Gatekeeper, and on Apple Silicon the wording is
  "damaged and can't be opened" — which sounds like a corrupt download rather
  than a policy decision. The user right-clicks the app and chooses Open, once.
  Only an Apple Developer certificate removes that; the README spells it out.
* Antivirus occasionally flags PyInstaller output on Windows. Set ONEFILE to
  False for a folder build, which is misread less often.
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

# Windows/Linux: one self-contained file. Set to False if antivirus objects.
# Ignored on macOS, where an .app bundle is a directory by definition.
ONEFILE = True

MAC = platform.system() == "Darwin"
WINDOWS = platform.system() == "Windows"


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

    say(f"  Building for {platform.system()} on {platform.machine()}.")
    say("  PyInstaller cannot cross-compile: this produces a build for THIS")
    say("  platform only. For the other one, push a tag and let")
    say("  .github/workflows/build.yml do it.")
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
        # macOS gets an .app bundle, which is a directory by definition and
        # must be --windowed to be a real double-clickable app rather than
        # something that opens a Terminal. Windows and Linux get one file with
        # a console, because that console is where a startup error is readable
        # and where the sign-in code appears when no email is configured.
        #
        # launch.py writes everything it says to veritagnosis.log as well, so
        # the windowed Mac build is not silent when something goes wrong.
        *(["--onedir", "--windowed",
           "--osx-bundle-identifier", "app.veritagnosis.desktop"]
          if MAC else
          [("--onefile" if ONEFILE else "--onedir"), "--console"]),
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

    if MAC:
        out = ROOT / "dist" / f"{NAME}.app"
    elif WINDOWS:
        out = ROOT / "dist" / f"{NAME}.exe"
    else:
        out = ROOT / "dist" / NAME
    say()
    say("  ----------------------------------------------------------")
    say(f"   Done:  {out}")
    say()
    say("   Give that to your client. They double-click it; nothing")
    say("   else is needed on their machine.")
    say()
    if MAC:
        say("   Zip it before sending (right-click -> Compress) so the")
        say("   bundle survives the trip in one piece.")
        say()
        say("   It is not signed, so the first open is refused: they")
        say("   right-click the app and choose Open, then Open again.")
        say("   Double-clicking first gives a misleading \"damaged\"")
        say("   message. Only an Apple Developer certificate avoids this.")
    elif WINDOWS:
        say("   It is not signed, so the first run shows SmartScreen:")
        say("   'More info' then 'Run anyway'.")
    say("  ----------------------------------------------------------")
    say()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
