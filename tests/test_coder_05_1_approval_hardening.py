"""CODER-05.1 approval replay and content/containment hardening.

No generated source is executed. All writes use pytest temporary directories.
"""

import hashlib
import os

import pytest

from core.chat.chat_architect import ChatArchitect
import core.chat.code_file_staging_v1 as staging
from core.chat.code_file_staging_v1 import (
    approve_staged_file,
    pending_proposal,
    reject_staged_file,
    reset_staging,
    stage_code_file,
)
from core.chat.project_code_file_writer_v1 import (
    create_project_code_file,
    extract_python_code,
)
from core.project.project_workspace_v1 import ProjectWorkspace


SOURCE = "def add(a, b):\n    return a + b\n"
OTHER = "def greet(name):\n    return 'hello ' + name\n"


@pytest.fixture(autouse=True)
def _clean_staging():
    reset_staging()
    yield
    reset_staging()


@pytest.fixture
def docs(tmp_path):
    path = tmp_path / "documents"
    path.mkdir()
    return str(path)


def _chat():
    return object.__new__(ChatArchitect)


def _dispatch(chat, text, project_id, creation_calls):
    approval = chat._authorized_code_file_approval(text, project_id)
    if approval:
        return approval
    creation_calls.append(text)
    return "creation-route"


@pytest.mark.parametrize(
    "text",
    [
        "تأیید می‌کنم، فایل calculator.py را ذخیره کن.",
        "Approve and save calculator.py.",
        "I confirm that calculator.py should be saved.",
    ],
)
def test_approval_with_no_pending_proposal_is_terminal(text):
    calls = []
    result = _dispatch(_chat(), text, "project_a", calls)

    assert calls == []
    assert "پیش‌نویس" in result or "pending" in result.lower()
    assert "نیست" in result or "no " in result.lower()


def test_repeated_approval_after_consumption_cannot_reenter_creation(docs):
    stage_code_file("project_a", "calculator.py", SOURCE, documents_root=docs)
    first = approve_staged_file(
        "project_a", "approve and save", documents_root=docs
    )
    before = hashlib.sha256(
        open(os.path.join(docs, "code", "calculator.py"), "rb").read()
    ).hexdigest()

    calls = []
    result = _dispatch(
        _chat(),
        "تأیید می‌کنم، فایل calculator.py را ذخیره کن.",
        "project_a",
        calls,
    )
    after = hashlib.sha256(
        open(os.path.join(docs, "code", "calculator.py"), "rb").read()
    ).hexdigest()

    assert first["status"] == "written"
    assert calls == []
    assert pending_proposal("project_a") is None
    assert before == after
    assert "پیش‌نویس" in result


def test_repeated_rejection_and_approval_after_rejection_are_terminal(docs):
    stage_code_file("project_a", "calculator.py", SOURCE, documents_root=docs)
    reject_staged_file("project_a", reason="user_rejected")

    calls = []
    rejected_again = _dispatch(_chat(), "Reject calculator.py.", "project_a", calls)
    approved_after = _dispatch(
        _chat(), "Approve and save calculator.py.", "project_a", calls
    )

    assert calls == []
    assert "پیش‌نویس" in rejected_again or "pending" in rejected_again.lower()
    assert "پیش‌نویس" in approved_after or "pending" in approved_after.lower()
    assert not os.path.exists(os.path.join(docs, "code", "calculator.py"))


def test_approval_in_wrong_project_is_terminal_and_does_not_consume_owner(docs):
    stage_code_file("project_owner", "calculator.py", SOURCE, documents_root=docs)

    calls = []
    result = _dispatch(
        _chat(), "Approve and save calculator.py.", "project_other", calls
    )

    assert calls == []
    assert pending_proposal("project_owner")["filename"] == "calculator.py"
    assert pending_proposal("project_other") is None
    assert "پیش‌نویس" in result or "pending" in result.lower()


def test_explicit_new_creation_requests_still_reach_creation_route():
    chat = _chat()

    for text in (
        "Create a new calculator.py program.",
        "Create an unrelated greeter.py file.",
        "فایل جدید greeter.py را ذخیره کن.",
    ):
        calls = []
        result = _dispatch(chat, text, "project_a", calls)
        assert result == "creation-route"
        assert calls == [text]


def test_mutating_returned_proposal_cannot_change_approved_bytes(docs):
    proposal = stage_code_file(
        "project_a", "calculator.py", SOURCE, documents_root=docs
    )
    proposal["content"] = "raise SystemExit('mutated')\n"

    outcome = approve_staged_file(
        "project_a", "approve and save", documents_root=docs
    )
    written = open(
        os.path.join(docs, "code", "calculator.py"), encoding="utf-8"
    ).read()

    assert outcome["status"] == "written"
    assert written == SOURCE
    assert outcome["digest"] == hashlib.sha256(SOURCE.encode("utf-8")).hexdigest()


def test_mutating_pending_projection_cannot_change_approved_bytes(docs):
    stage_code_file("project_a", "calculator.py", SOURCE, documents_root=docs)
    pending_proposal("project_a")["content"] = "print('mutated')\n"

    approve_staged_file("project_a", "approve and save", documents_root=docs)
    written = open(
        os.path.join(docs, "code", "calculator.py"), encoding="utf-8"
    ).read()

    assert written == SOURCE


def test_internal_digest_mismatch_fails_closed_without_write(docs):
    stage_code_file("project_a", "calculator.py", SOURCE, documents_root=docs)
    staging._STAGED["project_a"]["content"] = "print('tampered')\n"

    outcome = approve_staged_file(
        "project_a", "approve and save", documents_root=docs
    )

    assert outcome["status"] == "failed"
    assert outcome["reason"] == "staged_content_integrity_failed"
    assert outcome["writes_performed"] == 0
    assert not os.path.exists(os.path.join(docs, "code", "calculator.py"))


@pytest.mark.parametrize(
    "project_id",
    ["../escape", "..\\escape", "C:\\escape", "\\\\server\\share", "CON"],
)
def test_writer_rejects_unsafe_project_identifier_before_directory_creation(
    tmp_path, monkeypatch, project_id
):
    projects = tmp_path / "projects"
    workspace = ProjectWorkspace(
        projects_root=str(projects), trash_root=str(tmp_path / "trash")
    )
    import core.project.project_workspace_v1 as workspace_module

    monkeypatch.setattr(workspace_module, "project_workspace", workspace)

    result = create_project_code_file(project_id, "safe.py", SOURCE)

    assert result["status"] == "failed"
    assert result["reason"] == "invalid_project_id"
    assert list(tmp_path.rglob("safe.py")) == []


def test_staging_rejects_unsafe_project_identifier_without_making_sandbox(
    tmp_path, monkeypatch
):
    projects = tmp_path / "projects"
    workspace = ProjectWorkspace(
        projects_root=str(projects), trash_root=str(tmp_path / "trash")
    )
    import core.project.project_workspace_v1 as workspace_module

    monkeypatch.setattr(workspace_module, "project_workspace", workspace)

    proposal = stage_code_file("../escape", "safe.py", SOURCE)

    assert proposal["status"] == "rejected"
    assert proposal["reason"] == "invalid_project_id"
    assert not (tmp_path / "escape").exists()


def test_source_extraction_and_staging_bytes_are_deterministic(docs):
    model_text = (
        "```python\nprint('first')\n```\n"
        "commentary\n"
        "```py\nprint('second')\n\n```"
    )
    first = extract_python_code(model_text)
    second = extract_python_code(model_text)

    assert first == second == "print('second')"

    proposal = stage_code_file(
        "project_a", "second.py", first, documents_root=docs
    )
    assert proposal["content"] == first
    assert proposal["preview"] == first
    assert proposal["digest"] == hashlib.sha256(first.encode("utf-8")).hexdigest()

