"""CODER-05.1 offline acceptance and HTTP trust-boundary audit.

Recorded coder output only. Generated source is never executed or imported.
"""

import contextlib
import hashlib
import io
import os
import subprocess

import pytest

import app as application
import core.chat.chat_architect as chat_module
import core.chat.code_file_staging_v1 as staging
import core.chat.project_code_file_writer_v1 as writer
import core.vision.vision_provider_ollama_v1 as provider_module
from core.llm.llm_gateway import LLMGateway
from core.chat.session_registry_v1 import session_registry
from core.project.project_workspace_v1 import project_workspace


CALCULATOR = (
    "def add(a, b):\n"
    "    return a + b\n\n"
    "def subtract(a, b):\n"
    "    return a - b\n"
)
GREETER = "def greet(name):\n    return 'hello ' + name\n"
REJECTED = "print('must not be written')\n"
REPLACEMENT = "VALUE = 'replacement'\n"


class _RecordedCoder:
    def __init__(self):
        self.source = CALCULATOR
        self.calls = 0

    def generate(self, _prompt, **_kwargs):
        self.calls += 1
        return "```python\n%s```" % self.source


def _forbidden(label):
    def _raise(*_args, **_kwargs):
        raise AssertionError("unexpected call: " + label)

    return _raise


def _turn(text, session):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return application.chat.handle(text, context={"session_id": session})
    finally:
        # Direct calls bypass Flask's request boundary.  Release the
        # thread-local binding so unrelated tests cannot inherit this session.
        session_registry.end()


def _text(result):
    return str((result or {}).get("result") or "")


def _digest(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


@pytest.fixture
def isolated_runtime(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    trash = tmp_path / "trash"
    projects.mkdir()
    trash.mkdir()
    monkeypatch.setattr(project_workspace, "projects_root", str(projects))
    monkeypatch.setattr(project_workspace, "trash_root", str(trash))

    recorded = _RecordedCoder()
    monkeypatch.setattr(chat_module, "coder_gateway", lambda: recorded)
    monkeypatch.setattr(LLMGateway, "generate", _forbidden("general_llm"))
    monkeypatch.setattr(
        provider_module.OllamaVisionProvider, "analyze", _forbidden("vision")
    )
    monkeypatch.setattr(
        provider_module.OllamaVisualObserver, "observe", _forbidden("observer")
    )
    monkeypatch.setattr(
        provider_module.OllamaTextNormalizer, "normalize", _forbidden("normalizer")
    )
    monkeypatch.setattr(
        application.chat.render_runtime, "render", _forbidden("render")
    )
    monkeypatch.setattr(subprocess, "run", _forbidden("subprocess.run"))
    monkeypatch.setattr(subprocess, "Popen", _forbidden("subprocess.Popen"))

    writes = []
    stages = []
    real_write = writer.create_project_code_file
    real_stage = staging.stage_code_file

    def _write(*args, **kwargs):
        result = real_write(*args, **kwargs)
        writes.append(result)
        return result

    def _stage(*args, **kwargs):
        result = real_stage(*args, **kwargs)
        stages.append(result)
        return result

    monkeypatch.setattr(writer, "create_project_code_file", _write)
    monkeypatch.setattr(staging, "stage_code_file", _stage)
    staging.reset_staging()
    yield {
        "root": projects,
        "recorded": recorded,
        "writes": writes,
        "stages": stages,
    }
    staging.reset_staging()


def test_calculator_greeter_rejection_and_overwrite_acceptance(isolated_runtime):
    runtime = isolated_runtime
    session = "project_c051_acceptance"
    code_dir = runtime["root"] / session / "documents" / "code"

    # A — calculator: stage, preview/digest, approve exact bytes, replay stops.
    created = _turn("یک فایل واقعی calculator.py در پروژه بساز.", session)
    calc = code_dir / "calculator.py"
    assert not calc.exists()
    assert "SHA-256" in _text(created) and "پیش‌نمایش" in _text(created)
    staged_digest = staging.pending_proposal(session)["digest"]

    approved = _turn(
        "تأیید می‌کنم، فایل calculator.py را ذخیره کن.", session
    )
    assert calc.read_text(encoding="utf-8") == CALCULATOR.rstrip("\n")
    assert _digest(calc) == staged_digest
    assert "calculator.py" in _text(approved) and staged_digest in _text(approved)

    counts = (runtime["recorded"].calls, len(runtime["stages"]), len(runtime["writes"]))
    replay = _turn(
        "تأیید می‌کنم، فایل calculator.py را ذخیره کن.", session
    )
    assert "هیچ پیش‌نویس" in _text(replay)
    assert counts == (
        runtime["recorded"].calls,
        len(runtime["stages"]),
        len(runtime["writes"]),
    )
    assert staging.pending_proposal(session) is None

    # B — a genuinely new unrelated request still stages and writes.
    runtime["recorded"].source = GREETER
    _turn("یک فایل واقعی greeter.py در پروژه بساز.", session)
    _turn("تأیید می‌کنم، فایل greeter.py را ذخیره کن.", session)
    assert (code_dir / "greeter.py").read_text(encoding="utf-8") == GREETER.rstrip("\n")

    # C — reject consumes; later approval is a harmless no-pending response.
    runtime["recorded"].source = REJECTED
    staged_rejected = _turn("یک فایل واقعی rejected.py در پروژه بساز.", session)
    assert staging.pending_proposal(session) is not None, _text(staged_rejected)
    rejected = _turn("فایل rejected.py را رد کن.", session)
    assert "رد شد" in _text(rejected)
    calls_before = runtime["recorded"].calls
    after_reject = _turn("Approve and save rejected.py.", session)
    assert "هیچ پیش‌نویس" in _text(after_reject)
    assert runtime["recorded"].calls == calls_before
    assert not (code_dir / "rejected.py").exists()

    # D — an existing file requires a distinct overwrite confirmation.
    code_dir.mkdir(parents=True, exist_ok=True)
    replacement = code_dir / "replacement.py"
    replacement.write_text("VALUE = 'original'\n", encoding="utf-8")
    runtime["recorded"].source = REPLACEMENT
    _turn("یک فایل واقعی replacement.py در پروژه بساز.", session)
    ordinary = _turn("Approve and save replacement.py.", session)
    assert replacement.read_text(encoding="utf-8") == "VALUE = 'original'\n"
    assert staging.pending_proposal(session) is not None
    assert "نشد" in _text(ordinary) or "پیش‌نویس" in _text(ordinary)
    _turn("Approve and overwrite replacement.py.", session)
    assert replacement.read_text(encoding="utf-8") == REPLACEMENT.rstrip("\n")


def test_http_authorization_audit_proves_anonymous_actor_is_now_refused(
    isolated_runtime, monkeypatch
):
    """C05.2 closes the anonymous same-project approval path found by C05.1.

    The original C05.1 report/evidence remains unchanged. This live regression
    now retains its security value by requiring the formerly vulnerable request
    to stop before the writer while leaving the owner's proposal pending.
    """

    owner = project_workspace.create("Owner")
    other = project_workspace.create("Other")
    owner_id = owner["project_id"]
    other_id = other["project_id"]
    staging.stage_code_file(owner_id, "owned.py", CALCULATOR)

    attempts = []

    def _refuse_probe(**kwargs):
        attempts.append(kwargs)
        return {
            "status": "failed",
            "reason": "authorization_probe_refused",
            "verified_on_disk": False,
        }

    monkeypatch.setattr(writer, "create_project_code_file", _refuse_probe)
    client = application.app.test_client()

    with contextlib.redirect_stdout(io.StringIO()):
        wrong = client.post(
            "/api/chat",
            json={
                "text": "Approve and save owned.py.",
                "project_id": other_id,
            },
        )
    session_registry.end()
    assert wrong.status_code == 200
    assert attempts == []
    assert staging.pending_proposal(owner_id) is not None

    with contextlib.redirect_stdout(io.StringIO()):
        anonymous_same_project = client.post(
            "/api/chat",
            json={
                "text": "Approve and save owned.py.",
                "project_id": owner_id,
            },
        )
    session_registry.end()
    assert anonymous_same_project.status_code == 200
    assert attempts == []
    assert staging.pending_proposal(owner_id) is not None
    assert not (runtime_path := runtime_path_for(owner_id, "owned.py")).exists()


def runtime_path_for(project_id, filename):
    return (
        os_path(project_workspace.projects_root)
        / project_id
        / "documents"
        / "code"
        / filename
    )


def os_path(value):
    from pathlib import Path

    return Path(value)
