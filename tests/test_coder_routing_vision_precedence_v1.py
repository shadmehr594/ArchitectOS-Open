"""Regression: explicit code creation must outrank text-only image references.

The saved project_f043688f turn contains ordinary deictic/numbered prose in a
long Python/Tkinter specification.  The image-reference resolver sees that
prose as an image reference and, with no session images, used to return
``no_images_in_session`` before the existing Coder boundary was evaluated.

All generation in this module is recorded/mocked.  No generated source is
executed and the real project filesystem is never written.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess

import pytest

import app as application
import core.chat.chat_architect as chat_module
import core.chat.code_file_staging_v1 as staging
import core.chat.project_code_file_writer_v1 as writer
import core.vision.vision_provider_ollama_v1 as provider_module
from core.chat.chat_architect import ChatArchitect
from core.chat.session_registry_v1 import session_registry
from core.llm.llm_gateway import LLMGateway
from core.project.project_workspace_v1 import project_workspace
from core.vision.image_session_v1 import resolve_session_reference


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAT_JSON = os.path.join(
    ROOT,
    "data",
    "projects",
    "project_f043688f",
    "conversations",
    "chat.json",
)

RECORDED_SOURCE = """\
import tkinter as tk


def build_app():
    return tk.Tk()
"""


def _load_observed_failure() -> tuple[str, str]:
    with open(CHAT_JSON, encoding="utf-8") as handle:
        messages = json.load(handle)["messages"]

    for index in range(1, len(messages)):
        reply = str(messages[index].get("text") or "")
        if (
            messages[index].get("role") == "assistant"
            and "no_images_in_session" in reply
        ):
            request = messages[index - 1]
            if request.get("role") == "user" and "qwen3-coder:30b" in str(
                request.get("text") or ""
            ):
                return str(request["text"]), reply

    raise AssertionError("the observed Coder/Vision failure is absent from chat.json")


OBSERVED_REQUEST, OBSERVED_REPLY = _load_observed_failure()


class _RecordedCoder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate(self, prompt, **_kwargs):
        self.calls.append(str(prompt))
        return "```python\n%s```" % RECORDED_SOURCE


def _forbidden(label):
    def _raise(*_args, **_kwargs):
        raise AssertionError("unexpected call: " + label)

    return _raise


def _turn(text: str, session_id: str):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return application.chat.handle(
                text,
                context={"session_id": session_id},
            )
    finally:
        session_registry.end()


def _result_text(result) -> str:
    return str((result or {}).get("result") or "")


@pytest.fixture()
def isolated_runtime(tmp_path, monkeypatch, request):
    projects = tmp_path / "projects"
    trash = tmp_path / "trash"
    projects.mkdir()
    trash.mkdir()
    monkeypatch.setattr(project_workspace, "projects_root", str(projects))
    monkeypatch.setattr(project_workspace, "trash_root", str(trash))

    coder = _RecordedCoder()
    monkeypatch.setattr(chat_module, "coder_gateway", lambda: coder)
    monkeypatch.setattr(LLMGateway, "generate", _forbidden("general_llm"))
    monkeypatch.setattr(
        provider_module.OllamaVisionProvider,
        "analyze",
        _forbidden("vision"),
    )
    monkeypatch.setattr(
        provider_module.OllamaVisualObserver,
        "observe",
        _forbidden("observer"),
    )
    monkeypatch.setattr(
        provider_module.OllamaTextNormalizer,
        "normalize",
        _forbidden("vision_normalizer"),
    )
    monkeypatch.setattr(
        application.chat.render_runtime,
        "render",
        _forbidden("render"),
    )
    monkeypatch.setattr(
        writer,
        "create_project_code_file",
        _forbidden("file_write"),
    )
    monkeypatch.setattr(subprocess, "run", _forbidden("subprocess.run"))
    monkeypatch.setattr(subprocess, "Popen", _forbidden("subprocess.Popen"))

    stages = []
    real_stage = staging.stage_code_file

    def _stage(*args, **kwargs):
        proposal = real_stage(*args, **kwargs)
        stages.append(proposal)
        return proposal

    monkeypatch.setattr(staging, "stage_code_file", _stage)
    staging.reset_staging()
    node_digest = hashlib.sha256(request.node.nodeid.encode("utf-8")).hexdigest()[:16]
    session_id = "project_%s" % node_digest

    yield {
        "coder": coder,
        "projects": projects,
        "session_id": session_id,
        "stages": stages,
    }

    staging.reset_staging()
    session_registry.end()


def test_saved_failure_is_the_exact_observed_turn_and_normalizes_as_code():
    assert len(OBSERVED_REQUEST) == 3617
    assert "Python" in OBSERVED_REQUEST
    assert "Tkinter" in OBSERVED_REQUEST
    assert "documents/code/app.py" in OBSERVED_REQUEST
    assert "ذخیره نکن" in OBSERVED_REQUEST
    assert "اجرا نکن" in OBSERVED_REQUEST
    assert "no_images_in_session" in OBSERVED_REPLY

    payload = application.chat.input_adapter.normalize(OBSERVED_REQUEST, {})
    normalized = payload["text"]
    chat = object.__new__(ChatArchitect)
    chat.context = {}

    assert payload["raw_text"] == OBSERVED_REQUEST
    assert payload["normalization_applied"] is True
    assert chat._code_file_creation_turn(normalized) is True
    assert chat._staging_action_turn(normalized) is False

    # This records the collision that caused the regression.  It is not an
    # instruction to weaken the resolver for genuine image turns.
    reference = resolve_session_reference(
        "project_routing_empty_diagnostic",
        normalized,
    )
    assert reference["status"] == "unresolved"
    assert reference["reason"] == "no_images_in_session"
    assert reference["reference_kind"] == "active"


def test_exact_saved_request_reaches_coder_before_image_reference(isolated_runtime):
    runtime = isolated_runtime
    result = _turn(OBSERVED_REQUEST, runtime["session_id"])
    text = _result_text(result)

    assert len(runtime["coder"].calls) == 1
    assert len(runtime["stages"]) == 1
    assert "SHA-256" in text
    assert "no_images_in_session" not in text
    proposal = staging.pending_proposal(runtime["session_id"])
    assert proposal["filename"] == "app.py"
    assert proposal["status"] == "awaiting_approval"
    assert not list(runtime["projects"].rglob("app.py"))


@pytest.mark.parametrize(
    "text",
    [
        "یک برنامه Python جدید در فایل app.py بساز.",
        (
            "این نسخه جدید برنامه Python/Tkinter را تولید کن. "
            "1. رابط گرافیکی داشته باشد. 2. چهار عمل اصلی را انجام دهد. "
            "3. فایل app.py باشد."
        ),
        (
            "یک برنامه Python جدید در فایل app.py تولید کن؛ "
            "بدون تأیید من ذخیره نکن و کد را اجرا نکن."
        ),
    ],
)
def test_explicit_program_creation_without_images_stages_only(
    isolated_runtime,
    text,
):
    runtime = isolated_runtime
    result = _turn(text, runtime["session_id"])

    assert len(runtime["coder"].calls) == 1
    assert len(runtime["stages"]) == 1
    assert "SHA-256" in _result_text(result)
    assert staging.pending_proposal(runtime["session_id"]) is not None
    assert not list(runtime["projects"].rglob("app.py"))


def test_genuine_image_question_still_uses_image_reference_boundary(
    isolated_runtime,
):
    runtime = isolated_runtime
    result = _turn("تصویر اول را تحلیل کن", runtime["session_id"])

    assert "no_images_in_session" in _result_text(result)
    assert runtime["coder"].calls == []
    assert runtime["stages"] == []
    assert staging.pending_proposal(runtime["session_id"]) is None


@pytest.mark.parametrize(
    "text",
    [
        "تأیید می‌کنم، فایل app.py را ذخیره کن.",
        "فایل app.py را رد کن.",
    ],
)
def test_existing_approval_and_rejection_actions_do_not_call_coder(
    isolated_runtime,
    text,
):
    runtime = isolated_runtime
    result = _turn(text, runtime["session_id"])

    assert "هیچ پیش‌نویس" in _result_text(result)
    assert runtime["coder"].calls == []
    assert runtime["stages"] == []
    assert not list(runtime["projects"].rglob("*.py"))
