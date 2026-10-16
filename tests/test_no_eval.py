"""Nothing in the app may need eval() in the browser.

The Content-Security-Policy (security.CSP) leaves 'unsafe-eval' out on
purpose. Reflex's rx.call_script and rx.call_function both run their code with
eval(), so either one throws "EvalError ... 'unsafe-eval' is not an allowed
source of script" in the production build. The home-screen greeting did
exactly that. This keeps it from coming back.
"""

from __future__ import annotations

import re
from pathlib import Path

from veritagnosis import security

PKG = Path(__file__).resolve().parents[1] / "veritagnosis"
ASSETS = Path(__file__).resolve().parents[1] / "assets"


def test_the_csp_still_forbids_eval():
    assert "unsafe-eval" not in security.CSP


def test_no_python_code_asks_the_browser_to_eval():
    bad = []
    for f in PKG.rglob("*.py"):
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if re.search(r"\bcall_script\s*\(|\bcall_function\s*\(", code):
                bad.append(f"{f.relative_to(PKG)}:{n}")
    assert not bad, bad


def test_no_static_script_uses_eval():
    bad = []
    for f in ASSETS.rglob("*.js"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"\beval\s*\(|new\s+Function\s*\(", text):
            bad.append(f.name)
    assert not bad, bad


def test_readiness_scores_are_whole_numbers(monkeypatch):
    """A float here reached an int field on the profile screen and Reflex
    printed "Expected field 'ProfileState.readiness_overall' to receive type
    int, but got 51.0"."""
    from veritagnosis.services import insight
    monkeypatch.setattr(insight, "_assess_application_progress", lambda *a: 37.5)
    from veritagnosis import db
    from veritagnosis.models import User
    with db.get_session() as s:
        import uuid
        u = User(username=f"whole-{uuid.uuid4().hex[:10]}", password_hash="x")
        s.add(u); s.commit(); s.refresh(u)
        uid = u.id
    r = insight.assess(uid)
    for v in (r.academic, r.extracurricular, r.college_fit,
              r.application_progress, r.financial_readiness, r.overall):
        assert type(v) is int, (v, type(v))
