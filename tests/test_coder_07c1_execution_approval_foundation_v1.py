"""CODER-07C.1 — pure, offline execution-approval foundation.

No Flask route, Docker call, subprocess, generated-code execution, or model
provider is used.  All approval events in this suite are explicitly TEST-ONLY.
"""

import concurrent.futures
import hashlib
import os
import sys

import pytest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.chat.execution_approval_foundation_v1 import (  # noqa: E402
    ACTION_RUN_PYTHON,
    DEFAULT_RESOURCE_LIMITS,
    ExecutionApprovalLedger,
    RESOURCE_LIMIT_CEILINGS,
    SCOPE_EXECUTE,
)


SOURCE = b'print("approved bytes")\n'
PROJECT = "project_c07c1"


def trusted(actor="lsa_actor_a", session="lss_session_a", project=PROJECT):
    return {
        "trusted": True,
        "actor_id": actor,
        "session_id": session,
        "project_id": project,
    }


def setup_proposal(tmp_path, *, ledger=None, source=SOURCE):
    ledger = ledger or ExecutionApprovalLedger(test_mode=True)
    code_root = tmp_path / "code"
    code_root.mkdir(exist_ok=True)
    artifact = code_root / "calculator.py"
    artifact.write_bytes(source)
    digest = hashlib.sha256(source).hexdigest()
    save = {
        "status": "created",
        "verified_on_disk": True,
        "writes_performed": 1,
        "project_id": PROJECT,
        "filename": artifact.name,
        "digest": digest,
    }
    proposal = ledger.prepare_execution_approval(
        trusted_context=trusted(),
        project_id=PROJECT,
        authorized_code_root=str(code_root),
        artifact_path=str(artifact),
        verified_save=save,
        now=1000,
    )
    assert proposal["ok"] is True
    return ledger, code_root, artifact, proposal


def mint(tmp_path, *, ttl_seconds=120):
    ledger, code_root, artifact, proposal = setup_proposal(tmp_path)
    event = ledger.record_test_only_approval_event(
        proposal["proposal_id"], trusted(), now=1001,
        label="TEST-ONLY explicit execution approval",
    )
    assert event["ok"] is True
    capability = ledger.mint_execution_capability(
        proposal["proposal_id"], event["approval_event_id"],
        trusted_context=trusted(), now=1002, ttl_seconds=ttl_seconds,
    )
    assert capability["ok"] is True
    return ledger, code_root, artifact, proposal, event, capability


def consume(ledger, artifact, capability, **overrides):
    kwargs = {
        "capability_id": capability["capability_id"],
        "token": capability["token"],
        "trusted_context": trusted(),
        "project_id": PROJECT,
        "artifact_path": str(artifact),
        "source_sha256": capability["source_sha256"],
        "action": ACTION_RUN_PYTHON,
        "scope": SCOPE_EXECUTE,
        "resource_limits": dict(DEFAULT_RESOURCE_LIMITS),
        "now": 1003,
    }
    kwargs.update(overrides)
    return ledger.consume_execution_capability(**kwargs)


def test_verified_save_only_prepares_and_never_mints_execute_authority(tmp_path):
    ledger, root, artifact, proposal = setup_proposal(tmp_path)

    assert proposal["status"] == "awaiting_explicit_execution_approval"
    assert proposal["scope"] == SCOPE_EXECUTE
    assert "token" not in proposal
    assert ledger.inspect_status(proposal["proposal_id"], now=1000)["capability_minted"] is False


def test_only_a_separate_test_labelled_event_can_mint_offline(tmp_path):
    ledger, root, artifact, proposal = setup_proposal(tmp_path)

    refused = ledger.mint_execution_capability(
        proposal["proposal_id"], "caller_declared_user_approval",
        trusted_context=trusted(), now=1001,
    )
    assert refused["ok"] is False
    assert refused["reason"] == "trusted_approval_event_required"

    event = ledger.record_test_only_approval_event(
        proposal["proposal_id"], trusted(), now=1001,
        label="TEST-ONLY explicit execution approval",
    )
    assert event["event_kind"] == "TEST-ONLY"


def test_double_consumption_is_refused(tmp_path):
    ledger, root, artifact, proposal, event, capability = mint(tmp_path)

    assert consume(ledger, artifact, capability)["ok"] is True
    replay = consume(ledger, artifact, capability)
    assert replay["ok"] is False
    assert replay["reason"] == "execution_capability_consumed"


def test_concurrent_consumption_has_exactly_one_winner(tmp_path):
    ledger, root, artifact, proposal, event, capability = mint(tmp_path)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(
            lambda _index: consume(ledger, artifact, capability), range(8)))

    assert sum(item["ok"] is True for item in outcomes) == 1
    assert all(item["ok"] or item["reason"] == "execution_capability_consumed"
               for item in outcomes)


@pytest.mark.parametrize("field,value,reason", [
    ("actor_id", "lsa_actor_b", "execution_actor_mismatch"),
    ("session_id", "lss_session_b", "execution_session_mismatch"),
    ("project_id", "project_other", "execution_project_mismatch"),
])
def test_cross_binding_consumption_is_denied(tmp_path, field, value, reason):
    ledger, root, artifact, proposal, event, capability = mint(tmp_path)
    context = trusted()
    context[field] = value
    project = value if field == "project_id" else PROJECT

    outcome = consume(
        ledger, artifact, capability,
        trusted_context=context, project_id=project)

    assert outcome["ok"] is False
    assert outcome["reason"] == reason


def test_request_digest_mismatch_does_not_consume(tmp_path):
    ledger, root, artifact, proposal, event, capability = mint(tmp_path)

    refused = consume(
        ledger, artifact, capability, source_sha256="0" * 64)
    assert refused["reason"] == "execution_source_digest_mismatch"
    assert consume(ledger, artifact, capability)["ok"] is True


def test_source_changed_after_approval_is_refused(tmp_path):
    ledger, root, artifact, proposal, event, capability = mint(tmp_path)
    artifact.write_bytes(b'print("changed")\n')

    refused = consume(ledger, artifact, capability)

    assert refused["ok"] is False
    assert refused["reason"] == "execution_source_changed_after_approval"


def test_expired_capability_is_refused(tmp_path):
    ledger, root, artifact, proposal, event, capability = mint(
        tmp_path, ttl_seconds=10)

    refused = consume(ledger, artifact, capability, now=1013)

    assert refused["ok"] is False
    assert refused["reason"] == "execution_capability_expired"


def test_missing_trusted_context_and_self_declared_source_are_not_proof(tmp_path):
    ledger, root, artifact, proposal, event, capability = mint(tmp_path)

    for context in (None, {"source": "user", "issuer": "server_capability_ledger"}):
        refused = consume(
            ledger, artifact, capability, trusted_context=context)
        assert refused["reason"] == "trusted_local_context_required"


def test_save_scope_cannot_consume_execute_capability(tmp_path):
    ledger, root, artifact, proposal, event, capability = mint(tmp_path)

    refused = consume(ledger, artifact, capability, scope="save")

    assert refused["ok"] is False
    assert refused["reason"] == "execution_scope_mismatch"


def test_wrong_action_and_resource_limits_are_refused(tmp_path):
    ledger, root, artifact, proposal, event, capability = mint(tmp_path)

    assert consume(ledger, artifact, capability, action="shell")["reason"] == "execution_action_mismatch"
    raised = dict(DEFAULT_RESOURCE_LIMITS)
    raised["max_memory_mb"] += 1
    assert consume(
        ledger, artifact, capability,
        resource_limits=raised)["reason"] == "execution_resource_limits_mismatch"


def test_status_never_discloses_token_or_token_hash(tmp_path):
    ledger, root, artifact, proposal, event, capability = mint(tmp_path)

    status = ledger.inspect_status(capability["capability_id"], now=1003)

    assert status["ok"] is True
    assert "token" not in status
    assert "token_hash" not in status


def test_invalidation_and_restart_semantics_fail_closed(tmp_path):
    ledger, root, artifact, proposal, event, capability = mint(tmp_path)

    invalidated = ledger.invalidate_capability(
        capability["capability_id"], trusted_context=trusted(),
        reason="TEST-ONLY restart", now=1003)
    assert invalidated["ok"] is True
    assert consume(ledger, artifact, capability)["reason"] == "execution_capability_invalidated"

    fresh = ExecutionApprovalLedger(test_mode=True)
    assert consume(fresh, artifact, capability)["reason"] == "execution_capability_not_found"


def test_failure_after_atomic_claim_cannot_restore_or_replay_authority(tmp_path):
    ledger, root, artifact, proposal, event, capability = mint(tmp_path)

    def fail_after_claim():
        raise RuntimeError("TEST-ONLY injected consumption failure")

    failed = consume(
        ledger, artifact, capability,
        _test_only_fault_after_claim=fail_after_claim)

    assert failed["ok"] is False
    assert failed["reason"] == "execution_capability_consumption_failed"
    assert consume(ledger, artifact, capability)["reason"] == "execution_capability_consumed"


def test_unsafe_artifact_path_is_refused(tmp_path):
    ledger = ExecutionApprovalLedger(test_mode=True)
    code_root = tmp_path / "code"
    code_root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_bytes(SOURCE)
    digest = hashlib.sha256(SOURCE).hexdigest()

    refused = ledger.prepare_execution_approval(
        trusted_context=trusted(), project_id=PROJECT,
        authorized_code_root=str(code_root), artifact_path=str(outside),
        verified_save={
            "status": "created", "verified_on_disk": True,
            "writes_performed": 1, "project_id": PROJECT,
            "filename": "outside.py", "digest": digest,
        },
        now=1000,
    )

    assert refused["ok"] is False
    assert refused["reason"] == "unsafe_execution_artifact_path"


def test_live_module_has_no_route_or_dispatch_side_effects():
    import core.chat.execution_approval_foundation_v1 as module

    source = open(module.__file__, "r", encoding="utf-8").read().lower()
    assert "flask" not in source
    assert "subprocess" not in source
    assert "bounded_docker_orchestrator" not in source
    assert "execution_enabled = true" not in source


def test_resource_ceilings_match_the_disconnected_c07a_contract():
    from core.execution.execution_contract_v1 import LIMITS

    assert RESOURCE_LIMIT_CEILINGS == LIMITS
