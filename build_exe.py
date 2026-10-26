#!/usr/bin/env python3

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
        *(["--onedir", "--windowed",
           "--osx-bundle-identifier", "app.veritagnosis.desktop"]
          if MAC else
          [("--onefile" if ONEFILE else "--onedir"), "--console"]),
        # Laid out as <bundle>/web/build/client, which is what Reflex expects
        # under a web directory — launch.py points REFLEX_WEB_WORKDIR at it.
        f"--add-data={frontend}{sep}web/build/client",
        f"--add-data={ROOT / 'assets'}{sep}assets",
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
    icon = ROOT / "assets" / ("icon.icns" if platform.system() == "Darwin"
                              else "icon.ico")
    if icon.exists():
        args.append(f"--icon={icon}")
    else:
        say(f"      no {icon.name} — the app will carry PyInstaller's own icon")

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
