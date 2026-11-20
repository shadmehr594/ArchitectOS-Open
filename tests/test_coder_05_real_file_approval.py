"""CODER-05 — real file creation with an explicit approval boundary.

CPU only. No model inference (the coder gateway is recorded), no execution,
no shell, no packaging. Every write happens in a disposable temp directory.
"""

import hashlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.chat.code_file_staging_v1 import (
    APPROVAL_BLOCKED_MODEL_TEXT,
    STATUS_AWAITING_APPROVAL,
    STATUS_WRITTEN,
    approve_staged_file,
    pending_proposal,
    reject_staged_file,
    reset_staging,
    stage_code_file,
)

CALC_SOURCE = (
    "def add(a, b):\n"
    "    return a + b\n\n"
    "if __name__ == '__main__':\n"
    "    print(add(2, 3))\n"
)

OTHER_SOURCE = (
    "def greet(name):\n"
    "    return 'hello ' + name\n"
)


@pytest.fixture(autouse=True)
def _clean():
    reset_staging()
    yield
    reset_staging()


@pytest.fixture
def docs(tmp_path):
    root = tmp_path / "documents"
    root.mkdir()
    return str(root)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ==========================================================
# 1. STAGING — nothing is written before approval
# ==========================================================

def test_staging_proposes_and_writes_nothing(docs):
    proposal = stage_code_file(
        "proj-1", "calculator.py", CALC_SOURCE, documents_root=docs
    )

    assert proposal["status"] == STATUS_AWAITING_APPROVAL
    assert proposal["writes_performed"] == 0
    assert proposal["filename"] == "calculator.py"
    assert proposal["digest"] == _sha(CALC_SOURCE)
    assert proposal["content"] == CALC_SOURCE
    assert proposal["syntax_valid"] is True
    assert proposal["approval_token"]

    assert not os.path.exists(os.path.join(docs, "code", "calculator.py"))


def test_proposal_shows_a_preview_of_the_proposed_source(docs):
    proposal = stage_code_file("proj-1", "calculator.py", CALC_SOURCE, documents_root=docs)

    preview = proposal["preview"]

    assert "def add(a, b):" in preview
    assert preview == CALC_SOURCE


def test_staging_detects_existing_file_and_requires_overwrite_confirmation(tmp_path):
    root = tmp_path / "documents"
    (root / "code").mkdir(parents=True)
    (root / "code" / "calculator.py").write_text("# original\n", encoding="utf-8")

    proposal = stage_code_file(
        "proj-1", "calculator.py", CALC_SOURCE, documents_root=str(root)
    )

    assert proposal["status"] == STATUS_AWAITING_APPROVAL
    assert proposal["target_exists"] is True
    assert proposal["requires_overwrite_confirmation"] is True
    assert "original" in (proposal["diff"] or "")


# ==========================================================
# 2. EXPLICIT APPROVAL WRITES THE STAGED BYTES
# ==========================================================

def test_explicit_approval_writes_and_verifies_the_file(docs):
    proposal = stage_code_file("proj-1", "calculator.py", CALC_SOURCE, documents_root=docs)

    outcome = approve_staged_file(
        "proj-1", approval_text="تأیید می‌کنم، فایل را ذخیره کن.", documents_root=docs
    )

    assert outcome["status"] == STATUS_WRITTEN
    assert outcome["verified_on_disk"] is True
    assert outcome["digest"] == proposal["digest"]

    path = os.path.join(docs, "code", "calculator.py")

    assert os.path.exists(path)

    on_disk = open(path, "rb").read().decode("utf-8")

    assert on_disk == CALC_SOURCE
    assert hashlib.sha256(open(path, "rb").read()).hexdigest() == proposal["digest"]


def test_approval_is_single_use(docs):
    stage_code_file("proj-1", "calculator.py", CALC_SOURCE, documents_root=docs)

    first = approve_staged_file("proj-1", approval_text="approve and save", documents_root=docs)
    second = approve_staged_file("proj-1", approval_text="approve and save", documents_root=docs)

    assert first["status"] == STATUS_WRITTEN
    assert second["status"] == "failed"
    assert second["reason"] == "no_pending_proposal"
    assert second["writes_performed"] == 0


def test_without_approval_nothing_is_written(docs):
    stage_code_file("proj-1", "calculator.py", CALC_SOURCE, documents_root=docs)

    outcome = approve_staged_file(
        "proj-1", approval_text="چه فایلی پیشنهاد دادی؟", documents_root=docs
    )

    assert outcome["status"] == "failed"
    assert outcome["reason"] == "approval_not_expressed"
    assert not os.path.exists(os.path.join(docs, "code", "calculator.py"))


def test_model_text_claiming_approval_is_not_user_approval(docs):
    stage_code_file("proj-1", "calculator.py", CALC_SOURCE, documents_root=docs)

    outcome = approve_staged_file(
        "proj-1",
        approval_text="approved",
        documents_root=docs,
        approval_source="model",
    )

    assert outcome["status"] == "failed"
    assert outcome["reason"] == APPROVAL_BLOCKED_MODEL_TEXT
    assert not os.path.exists(os.path.join(docs, "code", "calculator.py"))


def test_rejection_discards_the_proposal(docs):
    stage_code_file("proj-1", "calculator.py", CALC_SOURCE, documents_root=docs)

    rejected = reject_staged_file("proj-1", reason="not what I wanted")

    assert rejected["status"] == "rejected"
    assert pending_proposal("proj-1") is None
    assert not os.path.exists(os.path.join(docs, "code", "calculator.py"))


def test_approval_is_project_bound(docs):
    stage_code_file("proj-1", "calculator.py", CALC_SOURCE, documents_root=docs)

    other = approve_staged_file(
        "proj-2", approval_text="approve and save", documents_root=docs
    )

    assert other["status"] == "failed"
    assert other["reason"] == "no_pending_proposal"


# ==========================================================
# 3. FILESYSTEM BOUNDARY
# ==========================================================

@pytest.mark.parametrize(
    "filename,reason",
    [
        ("../escape.py", "path_separator"),
        ("..\\escape.py", "path_separator"),
        ("C:\\Windows\\evil.py", "path_separator"),
        ("/etc/passwd.py", "path_separator"),
        ("con.py", "reserved_device_name"),
        ("not_python.txt", "unsafe_filename"),
        (".hidden.py", "unsafe_filename"),
        ("", "missing_filename"),
    ],
)
def test_unsafe_filenames_are_refused_at_staging(docs, filename, reason):
    proposal = stage_code_file("proj-1", filename, CALC_SOURCE, documents_root=docs)

    assert proposal["status"] == "rejected"
    assert proposal["reason"] == reason
    assert proposal["writes_performed"] == 0


def test_overwrite_needs_its_own_confirmation(tmp_path):
    root = tmp_path / "documents"
    (root / "code").mkdir(parents=True)
    target = root / "code" / "calculator.py"
    target.write_text("# original\n", encoding="utf-8")

    stage_code_file("proj-1", "calculator.py", CALC_SOURCE, documents_root=str(root))

    plain = approve_staged_file(
        "proj-1", approval_text="approve and save", documents_root=str(root)
    )

    assert plain["status"] == "failed"
    assert plain["reason"] == "overwrite_confirmation_required"
    assert target.read_text(encoding="utf-8") == "# original\n"

    confirmed = approve_staged_file(
        "proj-1",
        approval_text="approve and save",
        overwrite_confirmed=True,
        documents_root=str(root),
    )

    assert confirmed["status"] == STATUS_WRITTEN
    assert target.read_text(encoding="utf-8") == CALC_SOURCE


def test_failed_disk_write_reports_failure_not_success(docs, monkeypatch):
    stage_code_file("proj-1", "calculator.py", CALC_SOURCE, documents_root=docs)

    import core.chat.project_code_file_writer_v1 as writer

    real_replace = os.replace

    def _boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", _boom)

    outcome = approve_staged_file("proj-1", approval_text="approve and save", documents_root=docs)

    monkeypatch.setattr(os, "replace", real_replace)

    assert outcome["status"] == "failed"
    assert outcome["verified_on_disk"] is False
    assert not os.path.exists(os.path.join(docs, "code", "calculator.py"))


def test_staging_never_touches_architectos_production_sources(docs):
    before = hashlib.sha256(
        open("core/chat/project_code_file_writer_v1.py", "rb").read()
    ).hexdigest()

    stage_code_file("proj-1", "project_code_file_writer_v1.py", CALC_SOURCE, documents_root=docs)

    after = hashlib.sha256(
        open("core/chat/project_code_file_writer_v1.py", "rb").read()
    ).hexdigest()

    assert before == after


# ==========================================================
# 4. GENERALIZATION — not a calculator special case
# ==========================================================

def test_a_second_unrelated_source_file_is_staged_and_written(docs):
    proposal = stage_code_file("proj-1", "greeter.py", OTHER_SOURCE, documents_root=docs)

    assert proposal["status"] == STATUS_AWAITING_APPROVAL
    assert proposal["digest"] == _sha(OTHER_SOURCE)

    outcome = approve_staged_file("proj-1", approval_text="approve and save", documents_root=docs)

    assert outcome["status"] == STATUS_WRITTEN
    assert open(os.path.join(docs, "code", "greeter.py"), encoding="utf-8").read() == OTHER_SOURCE


def test_staged_content_is_what_gets_written_not_a_regenerated_version(docs):
    proposal = stage_code_file("proj-1", "calculator.py", CALC_SOURCE, documents_root=docs)

    # nothing can regenerate the content between approval and write
    outcome = approve_staged_file("proj-1", approval_text="approve and save", documents_root=docs)

    written = open(os.path.join(docs, "code", "calculator.py"), encoding="utf-8").read()

    assert written == proposal["content"]
    assert hashlib.sha256(written.encode("utf-8")).hexdigest() == proposal["digest"]


def test_invalid_python_is_staged_but_flagged(docs):
    proposal = stage_code_file("proj-1", "broken.py", "def oops(:\n", documents_root=docs)

    assert proposal["syntax_valid"] is False
    assert proposal["syntax_error"]
    assert proposal["writes_performed"] == 0
