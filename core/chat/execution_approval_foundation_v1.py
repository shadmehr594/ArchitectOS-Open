# -*- coding: utf-8 -*-
"""CODER-07C.1 offline execution-approval capability foundation.

This module owns only proposal and capability state.  It does not run source,
dispatch work, expose HTTP handlers, or turn a save approval into execution
authority.  A verified save can support a *proposal*; a distinct trusted
approval event is required before an execute-scoped token can be minted.

The only approval-event recorder implemented in this phase is deliberately
named and labelled TEST-ONLY.  Production browser approval integration remains
future work and cannot be inferred from a caller-authored ``source`` or
``issuer`` string.
"""

import hashlib
import math
import os
import secrets
import threading
import time

from core.chat.project_code_file_writer_v1 import (
    MAX_CODE_FILE_BYTES,
    _is_reparse_point,
    validate_code_filename,
    validate_project_id,
)


CONTRACT = "ExecutionApprovalFoundationV1"
VERSION = "1.0"
ACTION_RUN_PYTHON = "run_python"
SCOPE_EXECUTE = "execute"
MAX_CAPABILITY_TTL_SECONDS = 120
MAX_PROPOSAL_TTL_SECONDS = 120

# Kept local so the declarative C07A contract remains structurally disconnected
# from every production module.  A regression test asserts exact parity with
# that contract; this foundation does not import or activate it at runtime.
RESOURCE_LIMIT_CEILINGS = {
    "max_runtime_seconds": 30,
    "max_memory_mb": 512,
    "max_cpus": 1.0,
    "max_output_bytes": 65536,
    "max_pids": 64,
}

DEFAULT_RESOURCE_LIMITS = {
    "max_runtime_seconds": 10,
    "max_memory_mb": 256,
    "max_cpus": 1.0,
    "max_output_bytes": 65536,
    "max_pids": 32,
}

# Internal handoff key used only by the trusted-consent bridge after it has
# verified the existing UI-to-Core HMAC envelope. It is not an HTTP token and
# is never serialized.
_VERIFIED_APPROVAL_EVENT_KEY = object()


def _result(ok, reason=None, **values):
    answer = {
        "contract": CONTRACT,
        "version": VERSION,
        "ok": bool(ok),
        "reason": reason,
    }
    answer.update(values)
    return answer


def _now(value):
    value = time.time() if value is None else value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        if not math.isfinite(value):
            return None
    except (TypeError, ValueError, OverflowError):
        return None
    return float(value)


def _digest_bytes(content):
    return hashlib.sha256(content).hexdigest()


def _canonical(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def _safe_artifact(authorized_code_root, artifact_path):
    """Return a canonical direct-child Python artifact or ``None``."""
    if not isinstance(authorized_code_root, str) or not os.path.isabs(authorized_code_root):
        return None
    if not isinstance(artifact_path, str) or not os.path.isabs(artifact_path):
        return None
    root = _canonical(authorized_code_root)
    artifact = _canonical(artifact_path)
    if not os.path.isdir(root) or not os.path.isfile(artifact):
        return None
    if (_is_reparse_point(authorized_code_root)
            or _is_reparse_point(artifact_path)):
        return None
    if _canonical(os.path.dirname(artifact)) != root:
        return None
    filename = os.path.basename(artifact)
    filename_ok, _reason = validate_code_filename(filename)
    if not filename_ok:
        return None
    return artifact


def _read_artifact(path):
    try:
        if os.path.getsize(path) > MAX_CODE_FILE_BYTES:
            return None
        with open(path, "rb") as handle:
            content = handle.read(MAX_CODE_FILE_BYTES + 1)
        if len(content) > MAX_CODE_FILE_BYTES:
            return None
        return content
    except (OSError, ValueError):
        return None


def _resource_limits(value):
    if value is None:
        value = DEFAULT_RESOURCE_LIMITS
    if not isinstance(value, dict) or set(value) != set(RESOURCE_LIMIT_CEILINGS):
        return None
    normalized = {}
    for key, ceiling in RESOURCE_LIMIT_CEILINGS.items():
        number = value.get(key)
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            return None
        try:
            finite = math.isfinite(number)
        except (TypeError, ValueError, OverflowError):
            return None
        if not finite or number <= 0 or number > ceiling:
            return None
        normalized[key] = number
    return normalized


def _trusted_binding(context, project_id):
    """Projection of the existing server-verified local request context."""
    if not isinstance(context, dict) or context.get("trusted") is not True:
        return None
    actor = context.get("actor_id")
    session = context.get("session_id")
    context_project = context.get("project_id")
    if not isinstance(actor, str) or not actor.startswith("lsa_"):
        return None
    if not isinstance(session, str) or not session.startswith("lss_"):
        return None
    if context_project != project_id or not validate_project_id(project_id):
        return None
    return {
        "actor_id": actor,
        "session_id": session,
        "project_id": project_id,
    }


def _public_record(record, now=None):
    """Secret-free status projection."""
    if not isinstance(record, dict):
        return None
    status = record.get("status")
    current = _now(now)
    expires = record.get("expires_at")
    if (status == "active" and current is not None
            and isinstance(expires, (int, float)) and current > float(expires)):
        status = "expired"
    return {
        "record_type": record.get("record_type"),
        "proposal_id": record.get("proposal_id"),
        "capability_id": record.get("capability_id"),
        "status": status,
        "capability_minted": bool(record.get("capability_id")),
        "actor_id": record.get("actor_id"),
        "session_id": record.get("session_id"),
        "project_id": record.get("project_id"),
        "artifact_path": record.get("artifact_path"),
        "source_sha256": record.get("source_sha256"),
        "scope": record.get("scope"),
        "action": record.get("action"),
        "resource_limits": dict(record.get("resource_limits") or {}),
        "issued_at": record.get("issued_at"),
        "expires_at": record.get("expires_at"),
        "consumed": bool(record.get("consumed")),
        "invalidated": bool(record.get("invalidated")),
    }


class ExecutionApprovalLedger(object):
    """Short-lived, process-local, execute-only capability ledger."""

    def __init__(self, test_mode=False):
        self.test_mode = bool(test_mode)
        self._proposals = {}
        self._events = {}
        self._capabilities = {}
        self._lock = threading.RLock()
        self._generation = "eag_" + secrets.token_hex(12)

    def prepare_execution_approval(
        self,
        *,
        trusted_context,
        project_id,
        authorized_code_root,
        artifact_path,
        verified_save,
        resource_limits=None,
        now=None,
        proposal_ttl_seconds=MAX_PROPOSAL_TTL_SECONDS,
        expected_source_sha256=None,
    ):
        """Prepare review state.  Never creates an active capability."""
        current = _now(now)
        if current is None:
            return _result(False, "trusted_time_invalid")
        if (isinstance(proposal_ttl_seconds, bool)
                or not isinstance(proposal_ttl_seconds, (int, float))
                or not math.isfinite(proposal_ttl_seconds)
                or proposal_ttl_seconds <= 0
                or proposal_ttl_seconds > MAX_PROPOSAL_TTL_SECONDS):
            return _result(False, "execution_proposal_ttl_invalid")
        binding = _trusted_binding(trusted_context, project_id)
        if binding is None:
            return _result(False, "trusted_local_context_required")
        artifact = _safe_artifact(authorized_code_root, artifact_path)
        if artifact is None:
            return _result(False, "unsafe_execution_artifact_path")
        limits = _resource_limits(resource_limits)
        if limits is None:
            return _result(False, "execution_resource_limits_invalid")
        content = _read_artifact(artifact)
        if content is None:
            return _result(False, "execution_artifact_unreadable")
        digest = _digest_bytes(content)
        if expected_source_sha256 is not None:
            if (not isinstance(expected_source_sha256, str)
                    or not secrets.compare_digest(expected_source_sha256, digest)):
                return _result(False, "execution_source_digest_mismatch")

        save = verified_save if isinstance(verified_save, dict) else {}
        save_verified = (
            save.get("verified_on_disk") is True
            and save.get("status") in ("created", "overwritten", "written")
            and save.get("writes_performed") == 1
            and save.get("project_id") == project_id
            and save.get("filename") == os.path.basename(artifact)
            and isinstance(save.get("digest"), str)
            and secrets.compare_digest(save.get("digest"), digest)
        )
        if not save_verified:
            return _result(False, "verified_save_evidence_required")

        proposal_id = "eap_" + secrets.token_urlsafe(24)
        record = {
            "record_type": "proposal",
            "proposal_id": proposal_id,
            "capability_id": None,
            "status": "awaiting_explicit_execution_approval",
            "actor_id": binding["actor_id"],
            "session_id": binding["session_id"],
            "project_id": project_id,
            "authorized_code_root": _canonical(authorized_code_root),
            "artifact_path": artifact,
            "source_sha256": digest,
            "scope": SCOPE_EXECUTE,
            "action": ACTION_RUN_PYTHON,
            "resource_limits": limits,
            "issued_at": current,
            "expires_at": current + float(proposal_ttl_seconds),
            "consumed": False,
            "invalidated": False,
            "generation": self._generation,
        }
        with self._lock:
            self._proposals[proposal_id] = record
        return _result(True, None, **_public_record(record, current))

    def record_test_only_approval_event(
        self, proposal_id, trusted_context, *, now=None, label=None
    ):
        """Record synthetic approval evidence for offline tests only."""
        if not self.test_mode or "TEST-ONLY" not in str(label or ""):
            return _result(False, "test_only_approval_event_refused")
        return self._record_verified_approval_event(
            proposal_id,
            trusted_context,
            now=now,
            label=label,
            event_kind="TEST-ONLY",
            _verification_key=_VERIFIED_APPROVAL_EVENT_KEY,
        )

    def _record_verified_approval_event(
        self,
        proposal_id,
        trusted_context,
        *,
        now=None,
        label=None,
        event_kind=None,
        _verification_key=None
    ):
        """Internal event owner; only the HMAC-verifying bridge holds the key."""
        if _verification_key is not _VERIFIED_APPROVAL_EVENT_KEY:
            return _result(False, "verified_approval_event_required")
        if event_kind not in ("TEST-ONLY", "TRUSTED_LOCAL_UI_ACTION"):
            return _result(False, "approval_event_kind_invalid")
        current = _now(now)
        if current is None:
            return _result(False, "trusted_time_invalid")
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                return _result(False, "execution_proposal_not_found")
            if (proposal.get("generation") != self._generation
                    or proposal.get("invalidated")):
                return _result(False, "execution_proposal_invalidated")
            if current > float(proposal.get("expires_at") or 0):
                proposal["status"] = "expired"
                self._proposals[proposal_id] = proposal
                return _result(False, "execution_proposal_expired")
            if proposal.get("status") != "awaiting_explicit_execution_approval":
                return _result(False, "execution_proposal_not_awaiting_approval")
            binding = _trusted_binding(trusted_context, proposal["project_id"])
            if binding is None:
                return _result(False, "trusted_local_context_required")
            if (binding["actor_id"] != proposal["actor_id"]
                    or binding["session_id"] != proposal["session_id"]):
                return _result(False, "execution_approval_binding_mismatch")
            event_id = "tea_" + secrets.token_urlsafe(24)
            self._events[event_id] = {
                "approval_event_id": event_id,
                "event_kind": event_kind,
                "label": str(label),
                "proposal_id": proposal_id,
                "actor_id": binding["actor_id"],
                "session_id": binding["session_id"],
                "project_id": binding["project_id"],
                "recorded_at": current,
                "consumed": False,
                "generation": self._generation,
            }
        return _result(
            True, None, approval_event_id=event_id,
            event_kind=event_kind, proposal_id=proposal_id)

    def mint_execution_capability(
        self,
        proposal_id,
        approval_event_id,
        *,
        trusted_context,
        now=None,
        ttl_seconds=MAX_CAPABILITY_TTL_SECONDS
    ):
        """Mint once from a ledger-held approval event, never from text."""
        current = _now(now)
        if current is None:
            return _result(False, "trusted_time_invalid")
        if (isinstance(ttl_seconds, bool)
                or not isinstance(ttl_seconds, (int, float))
                or not math.isfinite(ttl_seconds)
                or ttl_seconds <= 0
                or ttl_seconds > MAX_CAPABILITY_TTL_SECONDS):
            return _result(False, "execution_capability_ttl_invalid")

        with self._lock:
            proposal = self._proposals.get(proposal_id)
            event = self._events.get(approval_event_id)
            if not proposal:
                return _result(False, "execution_proposal_not_found")
            if (proposal.get("generation") != self._generation
                    or proposal.get("invalidated")):
                return _result(False, "execution_proposal_invalidated")
            if current > float(proposal.get("expires_at") or 0):
                proposal["status"] = "expired"
                self._proposals[proposal_id] = proposal
                return _result(False, "execution_proposal_expired")
            binding = _trusted_binding(trusted_context, proposal["project_id"])
            if binding is None:
                return _result(False, "trusted_local_context_required")
            if not event or event.get("proposal_id") != proposal_id:
                return _result(False, "trusted_approval_event_required")
            if event.get("consumed"):
                return _result(False, "trusted_approval_event_consumed")
            if event.get("generation") != self._generation:
                return _result(False, "trusted_approval_event_invalidated")
            if any(binding[key] != proposal[key] or binding[key] != event[key]
                   for key in ("actor_id", "session_id", "project_id")):
                return _result(False, "execution_approval_binding_mismatch")
            if proposal.get("status") != "awaiting_explicit_execution_approval":
                return _result(False, "execution_proposal_not_awaiting_approval")

            content = _read_artifact(proposal["artifact_path"])
            if content is None or not secrets.compare_digest(
                    _digest_bytes(content), proposal["source_sha256"]):
                return _result(False, "execution_source_changed_before_approval")

            token = "exc_" + secrets.token_urlsafe(32)
            capability_id = "eca_" + secrets.token_urlsafe(24)
            capability = dict(proposal)
            capability.update({
                "record_type": "capability",
                "capability_id": capability_id,
                "status": "active",
                "token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                "issued_at": current,
                "expires_at": current + float(ttl_seconds),
                "consumed": False,
                "invalidated": False,
                "approval_event_id": approval_event_id,
            })
            event["consumed"] = True
            proposal["status"] = "capability_minted"
            proposal["capability_id"] = capability_id
            self._events[approval_event_id] = event
            self._proposals[proposal_id] = proposal
            self._capabilities[capability_id] = capability

        public = _public_record(capability, current)
        return _result(True, None, token=token, **public)

    def inspect_status(self, record_id, now=None):
        """Return a secret-free proposal or capability projection."""
        with self._lock:
            record = self._capabilities.get(record_id) or self._proposals.get(record_id)
            public = _public_record(record, now)
        if public is None:
            return _result(False, "execution_approval_record_not_found")
        return _result(True, None, **public)

    def consume_execution_capability(
        self,
        *,
        capability_id,
        token,
        trusted_context,
        project_id,
        artifact_path,
        source_sha256,
        action,
        scope,
        resource_limits,
        now=None,
        _test_only_fault_after_claim=None
    ):
        """Atomically claim exact execute authority.  Dispatches nothing."""
        current = _now(now)
        if current is None:
            return _result(False, "trusted_time_invalid")
        binding = _trusted_binding(trusted_context, project_id)
        if binding is None:
            return _result(False, "trusted_local_context_required")

        with self._lock:
            record = self._capabilities.get(capability_id)
            if not record:
                return _result(False, "execution_capability_not_found")
            if record.get("invalidated"):
                return _result(False, "execution_capability_invalidated")
            if record.get("consumed"):
                return _result(False, "execution_capability_consumed")
            if current > float(record.get("expires_at") or 0):
                record["status"] = "expired"
                self._capabilities[capability_id] = record
                return _result(False, "execution_capability_expired")
            if binding["actor_id"] != record["actor_id"]:
                return _result(False, "execution_actor_mismatch")
            if binding["session_id"] != record["session_id"]:
                return _result(False, "execution_session_mismatch")
            if project_id != record["project_id"]:
                return _result(False, "execution_project_mismatch")
            if scope != SCOPE_EXECUTE or scope != record["scope"]:
                return _result(False, "execution_scope_mismatch")
            if action != ACTION_RUN_PYTHON or action != record["action"]:
                return _result(False, "execution_action_mismatch")
            limits = _resource_limits(resource_limits)
            if limits is None or limits != record["resource_limits"]:
                return _result(False, "execution_resource_limits_mismatch")
            artifact = _safe_artifact(record["authorized_code_root"], artifact_path)
            if artifact is None or artifact != record["artifact_path"]:
                return _result(False, "execution_artifact_path_mismatch")
            if (not isinstance(source_sha256, str)
                    or not secrets.compare_digest(source_sha256, record["source_sha256"])):
                return _result(False, "execution_source_digest_mismatch")
            content = _read_artifact(artifact)
            if content is None or not secrets.compare_digest(
                    _digest_bytes(content), record["source_sha256"]):
                return _result(False, "execution_source_changed_after_approval")
            supplied_hash = hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()
            if not secrets.compare_digest(supplied_hash, record["token_hash"]):
                return _result(False, "execution_capability_invalid")

            # The claim precedes any future dispatch. An error after this point
            # cannot restore or replay authority.
            record["consumed"] = True
            record["status"] = "consumed"
            record["consumed_at"] = current
            self._capabilities[capability_id] = record
            if _test_only_fault_after_claim is not None:
                if not self.test_mode:
                    return _result(False, "test_only_fault_injection_refused")
                try:
                    _test_only_fault_after_claim()
                except Exception as exc:
                    record["status"] = "consumption_failed"
                    record["consumption_error"] = str(exc)[:200]
                    self._capabilities[capability_id] = record
                    return _result(False, "execution_capability_consumption_failed")

        return _result(
            True, None,
            capability_id=capability_id,
            status="consumed",
            source_sha256=record["source_sha256"],
            artifact_path=record["artifact_path"],
            action=record["action"],
            scope=record["scope"],
            resource_limits=dict(record["resource_limits"]),
            dispatch_performed=False,
            executed=False,
        )

    def invalidate_capability(
        self, capability_id, *, trusted_context, reason, now=None
    ):
        current = _now(now)
        if current is None:
            return _result(False, "trusted_time_invalid")
        with self._lock:
            record = self._capabilities.get(capability_id)
            if not record:
                return _result(False, "execution_capability_not_found")
            binding = _trusted_binding(trusted_context, record["project_id"])
            if binding is None:
                return _result(False, "trusted_local_context_required")
            if any(binding[key] != record[key]
                   for key in ("actor_id", "session_id", "project_id")):
                return _result(False, "execution_approval_binding_mismatch")
            record["invalidated"] = True
            record["status"] = "invalidated"
            record["invalidated_at"] = current
            record["invalidation_reason"] = str(reason or "explicit_invalidation")[:200]
            self._capabilities[capability_id] = record
        return _result(True, None, capability_id=capability_id, status="invalidated")

    def expire_capabilities(self, now=None):
        current = _now(now)
        if current is None:
            return _result(False, "trusted_time_invalid")
        expired = 0
        with self._lock:
            for capability_id, record in self._capabilities.items():
                if (record.get("status") == "active"
                        and current > float(record.get("expires_at") or 0)):
                    record["status"] = "expired"
                    self._capabilities[capability_id] = record
                    expired += 1
        return _result(True, None, expired=expired)

    def invalidate_all(self, reason="server_restart", now=None):
        """Fail closed on restart/shutdown; tokens never survive a new ledger."""
        current = _now(now)
        if current is None:
            return _result(False, "trusted_time_invalid")
        invalidated = 0
        with self._lock:
            for capability_id, record in self._capabilities.items():
                if not record.get("consumed") and not record.get("invalidated"):
                    record["invalidated"] = True
                    record["status"] = "invalidated"
                    record["invalidated_at"] = current
                    record["invalidation_reason"] = str(reason)[:200]
                    self._capabilities[capability_id] = record
                    invalidated += 1
            for proposal_id, record in self._proposals.items():
                if record.get("status") == "awaiting_explicit_execution_approval":
                    record["invalidated"] = True
                    record["status"] = "invalidated"
                    record["invalidated_at"] = current
                    record["invalidation_reason"] = str(reason)[:200]
                    self._proposals[proposal_id] = record
                    invalidated += 1
            self._events.clear()
            self._generation = "eag_" + secrets.token_hex(12)
        return _result(True, None, invalidated=invalidated)


def describe_foundation():
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "scope": SCOPE_EXECUTE,
        "action": ACTION_RUN_PYTHON,
        "max_ttl_seconds": MAX_CAPABILITY_TTL_SECONDS,
        "max_proposal_ttl_seconds": MAX_PROPOSAL_TTL_SECONDS,
        "default_resource_limits": dict(DEFAULT_RESOURCE_LIMITS),
        "save_automatically_mints_execute": False,
        "requires_separate_approval_event": True,
        "implemented_approval_event_kinds": ["TEST-ONLY"],
        "process_local": True,
        "single_use": True,
        "executes_anything": False,
        "exposes_routes": [],
        "production_integration": False,
    }
