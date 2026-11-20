"""CODER-05B — an expired proposal must still be rejectable.

The write-approval capability expires after ``approval_ttl_seconds`` (300 s in
production). Expiry must keep guarding the WRITE. It must not also make a
proposal impossible to discard, because a pending proposal blocks the creation
route and the user then cannot regenerate inside that project.

Contract pinned here:

* an authenticated, correctly bound user can reject an EXPIRED proposal;
* an expired proposal can never be approved or written;
* an untrusted / foreign actor, session or project cannot reject anything;
* the chat layer reports the REAL reject outcome, not a fixed success string;
* a successful rejection releases the pending slot so regeneration works.

No generated source is executed. Every write goes to a pytest temporary
directory via the ``documents_root`` seam, so no project sandbox is touched.
"""

import hashlib
import os
import time

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

SOURCE = "def add(a, b):\n    return a + b\n"
REGENERATED = "def sub(a, b):\n    return a - b\n"

SOURCE_DIGEST = hashlib.sha256(SOURCE.encode("utf-8")).hexdigest()

TTL = 300
T0 = 1_000_000.0


def _auth(actor="lsa_actor_a", session="lss_session_a", project="project_a"):
    return {
        "trusted": True,
        "actor_id": actor,
        "session_id": session,
        "project_id": project,
        "source": "trusted_local_ui_proxy",
    }


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


def _stage(docs, *, now=T0, content=SOURCE, project="project_a"):
    """Stage a bound proposal and return the proposal projection."""
    proposal = stage_code_file(
        project,
        "app.py",
        content,
        documents_root=docs,
        authorization=_auth(project=project),
        now=now,
        approval_ttl_seconds=TTL,
    )
    assert proposal["status"] == "awaiting_approval"
    return proposal


def _written(docs):
    return os.path.exists(os.path.join(docs, "code", "app.py"))


# --------------------------------------------------------------------------
# A. rejection works before AND after expiry
# --------------------------------------------------------------------------


def test_rejection_before_expiry_still_discards(docs):
    _stage(docs)

    outcome = reject_staged_file(
        "project_a", reason="user_rejected",
        authorization=_auth(), approval_token="irrelevant", now=T0 + 10,
    )

    assert outcome["status"] == "rejected"
    assert outcome["reason"] == "user_rejected"
    assert outcome["writes_performed"] == 0
    assert pending_proposal("project_a") is None


def test_rejection_after_expiry_discards_own_proposal(docs):
    """The regression: an expired proposal used to be un-rejectable forever."""
    _stage(docs)

    outcome = reject_staged_file(
        "project_a", reason="user_rejected",
        authorization=_auth(), approval_token="irrelevant", now=T0 + TTL + 1,
    )

    assert outcome["status"] == "rejected"
    assert pending_proposal("project_a") is None
    assert not _written(docs)


def test_rejection_after_a_long_expiry_still_discards(docs):
    """The live incident was ~37 minutes past expiry, not one second."""
    _stage(docs)

    outcome = reject_staged_file(
        "project_a", reason="user_rejected",
        authorization=_auth(), now=T0 + 2_200,
    )

    assert outcome["status"] == "rejected"
    assert pending_proposal("project_a") is None


def test_rejection_never_creates_the_code_directory(docs):
    _stage(docs)

    reject_staged_file("project_a", reason="user_rejected", authorization=_auth())

    assert not os.path.exists(os.path.join(docs, "code"))


# --------------------------------------------------------------------------
# B. expiry still denies the WRITE
# --------------------------------------------------------------------------


def test_expired_approval_is_still_denied(docs):
    proposal = _stage(docs)

    outcome = approve_staged_file(
        "project_a", "approve and save", documents_root=docs,
        authorization=_auth(), approval_token=proposal["approval_token"],
        now=T0 + TTL + 1,
    )

    assert outcome["status"] == "failed"
    assert outcome["reason"] == "approval_capability_expired"
    assert outcome["writes_performed"] == 0
    assert not _written(docs)
    # expiry denies the write but must not strand the proposal
    assert pending_proposal("project_a") is not None


def test_approval_inside_the_window_still_writes(docs):
    """The fix must not have weakened the happy path."""
    proposal = _stage(docs)

    outcome = approve_staged_file(
        "project_a", "approve and save", documents_root=docs,
        authorization=_auth(), approval_token=proposal["approval_token"],
        now=T0 + TTL - 1,
    )

    assert outcome["status"] == "written"
    assert outcome["verified_on_disk"] is True
    assert _written(docs)
    assert pending_proposal("project_a") is None


def test_rejection_cannot_be_used_as_write_authority(docs):
    """Rejecting must not leave behind anything that can still write."""
    _stage(docs)
    reject_staged_file(
        "project_a", reason="user_rejected",
        authorization=_auth(), now=T0 + TTL + 1,
    )

    after = approve_staged_file(
        "project_a", "approve and save", documents_root=docs,
        authorization=_auth(), approval_token="stg_forged", now=T0 + TTL + 2,
    )

    assert after["reason"] == "no_pending_proposal"
    assert not _written(docs)


# --------------------------------------------------------------------------
# C. rejection stays unavailable to unauthorized / foreign callers
# --------------------------------------------------------------------------


def test_untrusted_caller_cannot_reject(docs):
    _stage(docs)

    outcome = reject_staged_file("project_a", reason="user_rejected")

    assert outcome["status"] == "failed"
    assert outcome["reason"] == "trusted_authorization_required"
    assert pending_proposal("project_a") is not None


def test_foreign_actor_cannot_reject_even_when_expired(docs):
    _stage(docs)

    outcome = reject_staged_file(
        "project_a", reason="user_rejected",
        authorization=_auth(actor="lsa_actor_intruder"), now=T0 + TTL + 1,
    )

    assert outcome["status"] == "failed"
    assert outcome["reason"] == "approval_actor_mismatch"
    assert pending_proposal("project_a") is not None


def test_foreign_session_cannot_reject_even_when_expired(docs):
    _stage(docs)

    outcome = reject_staged_file(
        "project_a", reason="user_rejected",
        authorization=_auth(session="lss_session_intruder"), now=T0 + TTL + 1,
    )

    assert outcome["status"] == "failed"
    assert outcome["reason"] == "approval_session_mismatch"
    assert pending_proposal("project_a") is not None


def test_wrong_project_cannot_reject_even_when_expired(docs):
    _stage(docs)

    outcome = reject_staged_file(
        "project_a", reason="user_rejected",
        authorization=_auth(project="project_b"), now=T0 + TTL + 1,
    )

    assert outcome["status"] == "failed"
    assert outcome["reason"] == "trusted_authorization_required"
    assert pending_proposal("project_a") is not None


# --------------------------------------------------------------------------
# D. the chat layer reports the real reject outcome
# --------------------------------------------------------------------------


def _chat(authorization, capability=None):
    chat = object.__new__(ChatArchitect)
    chat.context = {"trusted_local_authorization": authorization}
    if capability is not None:
        chat.context["approval_capability"] = capability
    return chat


def test_chat_rejects_an_already_expired_proposal(docs):
    """End-to-end through the real chat path; staging happened long ago."""
    stage_code_file(
        "project_a", "app.py", SOURCE, documents_root=docs,
        authorization=_auth(), now=time.time() - (TTL + 900),
        approval_ttl_seconds=TTL,
    )

    reply = _chat(_auth())._authorized_code_file_approval("رد کن", "project_a")

    assert "رد شد" in reply
    assert pending_proposal("project_a") is None
    assert not _written(docs)


def test_chat_does_not_claim_success_when_rejection_fails(docs):
    _stage(docs)
    foreign = _auth(session="lss_session_intruder")

    reply = _chat(foreign)._authorized_code_file_approval("رد کن", "project_a")

    assert "رد نشد" in reply
    assert "approval_session_mismatch" in reply
    assert "رد شد و" not in reply
    assert pending_proposal("project_a") is not None


def test_chat_reports_untrusted_rejection_truthfully(docs):
    _stage(docs)
    chat = object.__new__(ChatArchitect)  # no trusted context at all

    reply = chat._authorized_code_file_approval("رد کن", "project_a")

    assert reply is not None
    assert "رد نشد" in reply
    assert "trusted_authorization_required" in reply
    assert pending_proposal("project_a") is not None


# --------------------------------------------------------------------------
# E. successful rejection releases the pending slot
# --------------------------------------------------------------------------


def test_regeneration_is_allowed_after_expired_rejection(docs):
    _stage(docs)
    reject_staged_file(
        "project_a", reason="user_rejected",
        authorization=_auth(), now=T0 + TTL + 1,
    )
    assert pending_proposal("project_a") is None

    second = _stage(docs, now=T0 + TTL + 2, content=REGENERATED)

    assert second["digest"] != SOURCE_DIGEST
    assert pending_proposal("project_a") is not None
    assert pending_proposal("project_a")["digest"] == second["digest"]
