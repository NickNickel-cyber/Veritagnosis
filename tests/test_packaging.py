"""
The packaged app: where it puts data, and what it refuses to do.

These matter because the failure they prevent is silent. A packaged app that
writes the student's database into its own temporary extraction directory
loses every essay when the window closes, and the next launch looks like a
fresh install rather than a bug.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import launch  # noqa: E402


# --------------------------------------------------------------- data location

def test_unfrozen_keeps_data_in_the_project_folder(monkeypatch):
    monkeypatch.setattr(launch.sys, "frozen", False, raising=False)
    monkeypatch.setattr(launch, "frozen", lambda: False)
    assert launch._beside_the_app() == Path(launch.__file__).resolve().parent


def test_a_mac_app_bundle_writes_OUTSIDE_itself(monkeypatch):
    """The bug this prevents.

    On macOS the executable sits at Veritagnosis.app/Contents/MacOS/Veritagnosis.
    Treating "beside the executable" literally would put the student's database
    inside the application bundle, where replacing the app deletes it — and
    where an app in /Applications cannot write at all.
    """
    monkeypatch.setattr(launch, "frozen", lambda: True)
    fake = "/Applications/Veritagnosis.app/Contents/MacOS/Veritagnosis"
    monkeypatch.setattr(launch.sys, "executable", fake)
    assert launch._beside_the_app() == Path("/Applications")


def test_a_windows_exe_writes_beside_itself(monkeypatch):
    monkeypatch.setattr(launch, "frozen", lambda: True)
    monkeypatch.setattr(launch.sys, "executable",
                        "/home/student/Desktop/Veritagnosis")
    assert launch._beside_the_app() == Path("/home/student/Desktop")


def test_an_unwritable_location_falls_back_to_the_user_folder(monkeypatch, tmp_path):
    """An app in /Applications or Program Files must still start."""
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    fallback = tmp_path / "userdata"

    monkeypatch.setattr(launch, "_beside_the_app", lambda: blocked)
    monkeypatch.setattr(launch, "_user_data_dir", lambda: fallback)

    real_write = Path.write_text

    def refuse(self, *a, **kw):
        if blocked in self.parents:
            raise OSError("read-only file system")
        return real_write(self, *a, **kw)

    monkeypatch.setattr(Path, "write_text", refuse)
    assert launch.home_dir() == fallback
    assert fallback.exists()


def test_a_writable_location_is_preferred_and_left_clean(monkeypatch, tmp_path):
    monkeypatch.setattr(launch, "_beside_the_app", lambda: tmp_path)
    monkeypatch.setattr(launch, "_user_data_dir", lambda: tmp_path / "nope")
    assert launch.home_dir() == tmp_path
    # the writability probe must not leave litter behind
    assert not (tmp_path / ".vg-write-test").exists()


@pytest.mark.parametrize("system,expect", [
    ("Windows", "Veritagnosis"),
    ("Darwin", "Application Support"),
    ("Linux", "veritagnosis"),
])
def test_each_platform_uses_its_own_conventional_folder(monkeypatch, system, expect):
    monkeypatch.setattr(launch.platform, "system", lambda: system)
    assert expect in str(launch._user_data_dir())


# ------------------------------------------------------------- no console

def test_saying_something_without_a_console_does_not_raise(monkeypatch, tmp_path):
    """A windowed macOS .app has no stdout. say() must still work, and must
    still record what it said, or a startup failure is invisible."""
    monkeypatch.setattr(launch, "HOME", tmp_path)
    monkeypatch.setattr(launch, "_LOG", None)

    def explode(*a, **kw):
        raise OSError("no console")

    monkeypatch.setattr("builtins.print", explode)
    launch.say("hello from a windowed app")      # must not raise
    log = tmp_path / "veritagnosis.log"
    assert log.exists()
    assert "hello from a windowed app" in log.read_text(encoding="utf-8")


def test_pause_does_not_block_when_there_is_no_console(monkeypatch):
    """input() in a windowed .app raises, and a build that paused on error
    would hang forever with no window to type into."""
    monkeypatch.setattr(launch, "has_console", lambda: False)

    def explode(*a, **kw):
        raise AssertionError("pause() called input() with no console")

    monkeypatch.setattr("builtins.input", explode)
    launch.pause()          # must return quietly


# ------------------------------------------------------- the launcher files

ROOT = Path(__file__).resolve().parent.parent


def test_both_platform_launchers_exist():
    assert (ROOT / "Veritagnosis.bat").exists(), "Windows launcher missing"
    assert (ROOT / "Veritagnosis.command").exists(), "macOS launcher missing"


def test_the_mac_launcher_is_executable():
    """Without the execute bit macOS opens a .command in TextEdit instead of
    running it, which looks exactly like a broken app."""
    launcher = ROOT / "Veritagnosis.command"
    assert os.access(launcher, os.X_OK), (
        "Veritagnosis.command is not executable — double-clicking it on macOS "
        "will open a text editor")


def test_the_windows_only_launchers_are_gone():
    """Replaced by the cross-platform pair. Leaving them would give a Mac user
    files that cannot work and a choice they should not have to make."""
    for dead in ("run.bat", "fix_env.bat", "deploy.bat", "start.sh"):
        assert not (ROOT / dead).exists(), f"{dead} should have been removed"


def test_the_launchers_do_not_hardcode_a_python_path():
    """They must find whatever Python the user has, not one developer's."""
    for name in ("Veritagnosis.bat", "Veritagnosis.command"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert ".venv" not in text, f"{name} must not assume a venv exists yet"
        assert "C:\\\\Users" not in text and "/Users/" not in text


def test_the_build_workflow_covers_both_platforms():
    wf = ROOT / ".github" / "workflows" / "build.yml"
    assert wf.exists(), "no CI workflow — there is then no way to build for Mac"
    text = wf.read_text(encoding="utf-8")
    assert "windows-latest" in text
    assert "macos-latest" in text


# ------------------------------------------------------- where the data lives

def _db_url_from(cwd, env=None):
    """Load rxconfig.py in a child process with that working directory."""
    import subprocess, textwrap
    code = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        import rxconfig
        print(rxconfig.config.db_url)
    """)
    e = dict(os.environ)
    e.pop("VG_DB_URL", None)
    e.pop("VG_BASE_DIR", None)
    e.update(env or {})
    out = subprocess.run([sys.executable, "-c", code], cwd=str(cwd),
                         capture_output=True, text=True, env=e)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def test_the_database_path_does_not_depend_on_where_the_app_was_started(tmp_path):
    """The bug this prevents: a relative sqlite path is resolved against the
    PROCESS WORKING DIRECTORY, so the app had one database per folder it was
    ever launched from. Every one of them looked like a brand-new install —
    no account, no essays, no checkpoints — and nothing was ever actually
    lost, which made it that much harder to recognise."""
    from_project = _db_url_from(ROOT)
    from_elsewhere = _db_url_from(tmp_path)
    assert from_project == from_elsewhere, (
        "the database moves with the working directory: "
        f"{from_project} vs {from_elsewhere}")
    assert from_project.startswith("sqlite:////") or ":" in from_project[10:], \
        f"not an absolute path: {from_project}"
    assert str(ROOT) in from_project or ROOT.as_posix() in from_project


def test_a_packaged_app_keeps_its_data_beside_the_executable(tmp_path):
    """launch.py sets VG_BASE_DIR to the folder the executable sits in,
    because inside a one-file bundle the code lives in a temporary directory
    the operating system deletes on exit. The database has to follow it."""
    url = _db_url_from(tmp_path, env={"VG_BASE_DIR": str(tmp_path)})
    assert tmp_path.as_posix() in url, url
    assert (tmp_path / "data").is_dir(), "the data folder should be created"


# --------------------------------------------------------------------- brand

def test_the_logo_ships_in_every_form_the_app_needs():
    """Four files, four jobs: the splash crest, the browser tab, the Windows
    executable's own icon and the Mac app's. A missing one is not an error
    anywhere — the page shows a broken image, the tab shows a blank page icon
    and the app carries PyInstaller's logo — so it is checked here."""
    assets = ROOT / "assets"
    for name, floor in (("logo.png", 20_000), ("favicon.png", 500),
                        ("icon.ico", 10_000), ("icon.icns", 10_000)):
        f = assets / name
        assert f.exists(), f"{name} is missing"
        assert f.stat().st_size > floor, f"{name} is too small to be the artwork"


def test_the_icns_is_a_real_icns():
    """Written by hand rather than by iconutil, which only exists on a Mac.
    If the header is wrong PyInstaller fails the Mac build, and that failure
    happens on a CI runner nobody is watching."""
    import struct
    data = (ROOT / "assets" / "icon.icns").read_bytes()
    assert data[:4] == b"icns"
    assert struct.unpack(">I", data[4:8])[0] == len(data), "length field is wrong"
    seen, off = [], 8
    while off < len(data):
        code = data[off:off + 4]
        size = struct.unpack(">I", data[off + 4:off + 8])[0]
        assert size >= 8 and off + size <= len(data), f"bad chunk at {off}"
        seen.append(code)
        off += size
    assert b"ic08" in seen, "no 256px icon, which is the one Finder shows"


def test_the_splash_shows_the_logo_and_not_a_letter():
    page = (ROOT / "veritagnosis" / "pages" / "auth.py").read_text(encoding="utf-8")
    assert '"/logo.png"' in page, "the splash is not pointing at the logo"
    assert 'rx.box("V", class_name="emblem")' not in page, "the painted V is back"


def test_the_executable_icon_matches_the_platform():
    """PyInstaller stops with an error when handed an .ico on macOS, so this
    is a build failure rather than a cosmetic slip."""
    build = (ROOT / "build_exe.py").read_text(encoding="utf-8")
    assert "icon.icns" in build and "icon.ico" in build
    assert 'platform.system() == "Darwin"' in build
