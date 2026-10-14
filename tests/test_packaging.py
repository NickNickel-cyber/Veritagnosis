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
