"""CODER-07C.2 focused review of the accepted C07C.1 foundation.

These tests are offline.  Source files are inert bytes and are never imported
or executed.
"""

import hashlib

import core.chat.execution_approval_foundation_v1 as foundation


SOURCE = b'print("inert")\n'
PROJECT = "project_c07c2"


def _trusted():
    return {
        "trusted": True,
        "actor_id": "lsa_c07c2_actor",
        "session_id": "lss_c07c2_session",
        "project_id": PROJECT,
    }


def _prepare(tmp_path, *, now=1000):
    root = tmp_path / "code"
    root.mkdir()
    artifact = root / "review.py"
    artifact.write_bytes(SOURCE)
    digest = hashlib.sha256(SOURCE).hexdigest()
    ledger = foundation.ExecutionApprovalLedger(test_mode=True)
    result = ledger.prepare_execution_approval(
        trusted_context=_trusted(),
        project_id=PROJECT,
        authorized_code_root=str(root),
        artifact_path=str(artifact),
        verified_save={
            "status": "created",
            "verified_on_disk": True,
            "writes_performed": 1,
            "project_id": PROJECT,
            "filename": artifact.name,
            "digest": digest,
        },
        now=now,
    )
    return ledger, root, artifact, result


def test_proposal_has_a_short_review_expiry(tmp_path):
    _ledger, _root, _artifact, proposal = _prepare(tmp_path)

    assert proposal["ok"] is True
    assert proposal["expires_at"] == 1120.0


def test_expired_proposal_cannot_record_approval_event(tmp_path):
    ledger, _root, _artifact, proposal = _prepare(tmp_path)

    result = ledger.record_test_only_approval_event(
        proposal["proposal_id"],
        _trusted(),
        now=1121,
        label="TEST-ONLY explicit consent",
    )

    assert result["ok"] is False
    assert result["reason"] == "execution_proposal_expired"


def test_invalidate_all_invalidates_unminted_proposals(tmp_path):
    ledger, _root, _artifact, proposal = _prepare(tmp_path)
    assert ledger.invalidate_all(now=1001)["ok"] is True

    result = ledger.record_test_only_approval_event(
        proposal["proposal_id"],
        _trusted(),
        now=1002,
        label="TEST-ONLY explicit consent",
    )

    assert result["ok"] is False
    assert result["reason"] == "execution_proposal_invalidated"


def test_windows_reparse_artifact_is_refused_even_when_islink_is_false(
    tmp_path, monkeypatch
):
    ledger, root, artifact, _proposal = _prepare(tmp_path)
    digest = hashlib.sha256(SOURCE).hexdigest()
    real_reparse_check = foundation._is_reparse_point

    monkeypatch.setattr(
        foundation,
        "_is_reparse_point",
        lambda path: str(path) == str(artifact) or real_reparse_check(path),
    )
    result = ledger.prepare_execution_approval(
        trusted_context=_trusted(),
        project_id=PROJECT,
        authorized_code_root=str(root),
        artifact_path=str(artifact),
        verified_save={
            "status": "created",
            "verified_on_disk": True,
            "writes_performed": 1,
            "project_id": PROJECT,
            "filename": artifact.name,
            "digest": digest,
        },
        now=1000,
    )

    assert result["ok"] is False
    assert result["reason"] == "unsafe_execution_artifact_path"
