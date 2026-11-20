# -*- coding: utf-8 -*-
"""CODER-07C.2 internal trusted-consent bridge (offline only).

The bridge verifies the existing UI-to-Core HMAC envelope and projects that
verified identity into the C07C.1 execution-approval ledger.  It registers no
route, is not imported by live chat dispatch, and performs no execution.

Only the explicitly TEST-ONLY consent method can create an approval event in
this phase.  A signed proxy request authenticates the existing local trust
domain; it is not, by itself, proof of a real browser click.
"""

import os
import re
import threading

from core.chat.execution_approval_foundation_v1 import (
    ACTION_RUN_PYTHON,
    DEFAULT_RESOURCE_LIMITS,
    MAX_CAPABILITY_TTL_SECONDS,
    SCOPE_EXECUTE,
    ExecutionApprovalLedger,
    _VERIFIED_APPROVAL_EVENT_KEY,
)
from core.chat.project_code_file_writer_v1 import (
    validate_code_filename,
    validate_project_id,
)
from core.runtime.local_authorization_v1 import verify_proxy_request


CONTRACT = "TrustedExecutionConsentBridgeV1"
VERSION = "1.0"
PREVIEW_PATH = "/api/coder/execution/preview"
CONSENT_PATH = "/api/coder/execution/consent"
CONSUME_PATH = "/internal/coder/execution-capability-claim"

_PREVIEW_FIELDS = {
    "operation", "project_id", "filename", "source_sha256", "action",
    "scope", "resource_limits",
}
_CONSENT_FIELDS = {
    "operation", "proposal_id", "project_id", "filename",
    "source_sha256", "action", "scope", "consent",
}
_CONSUME_FIELDS = {
    "operation", "capability_id", "project_id", "filename",
    "source_sha256", "action", "scope", "resource_limits",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_LIVE_PREVIEW_FIELDS = {"operation", "project_id", "filename"}
_LIVE_CONSENT_FIELDS = {
    "operation", "proposal_id", "project_id", "filename",
    "source_sha256", "action", "scope", "consent",
}


def _result(ok, reason=None, **values):
    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "ok": bool(ok),
        "reason": reason,
    }
    result.update(values)
    return result


def _trusted_context(verified, project_id):
    return {
        "trusted": True,
        "actor_id": verified["actor_id"],
        "session_id": verified["session_id"],
        "project_id": project_id,
        "source": "trusted_local_ui_proxy",
    }


def _valid_digest(value):
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _valid_filename(value):
    if not isinstance(value, str):
        return False
    valid, _reason = validate_code_filename(value)
    return bool(valid)


def _verify_request(secret, headers, payload, path, remote_addr, now, nonce_ledger):
    return verify_proxy_request(
        secret,
        headers,
        payload,
        path=path,
        remote_addr=remote_addr,
        now=now,
        nonce_ledger=nonce_ledger,
    )


class TrustedExecutionConsentBridge(object):
    """Internal handoff from verified proxy requests to one C07C.1 ledger."""

    def __init__(self, test_mode=False, ledger=None):
        self.test_mode = bool(test_mode)
        self.ledger = ledger or ExecutionApprovalLedger(test_mode=self.test_mode)
        # Server-side raw-token custody only. Permission state remains owned by
        # the foundation ledger, so this is not a second authorization store.
        self._capability_tokens = {}
        self._capability_bindings = {}
        self._lock = threading.RLock()

    def _store_capability(self, capability, context):
        capability_id = capability["capability_id"]
        with self._lock:
            self._capability_tokens[capability_id] = capability["token"]
            self._capability_bindings[capability_id] = {
                "trusted_context": dict(context),
                "project_id": capability["project_id"],
                "artifact_path": capability["artifact_path"],
                "source_sha256": capability["source_sha256"],
                "action": capability["action"],
                "scope": capability["scope"],
                "resource_limits": dict(capability["resource_limits"]),
                "expires_at": capability["expires_at"],
            }

    def prepare_preview(
        self,
        *,
        proxy_secret,
        headers,
        payload,
        path,
        remote_addr,
        nonce_ledger,
        project_id,
        authorized_code_root,
        artifact_path,
        verified_save,
        now=None,
    ):
        verified = _verify_request(
            proxy_secret, headers, payload, path, remote_addr, now, nonce_ledger)
        if not verified.get("trusted"):
            return _result(False, verified.get("reason"))
        if path != PREVIEW_PATH:
            return _result(False, "execution_preview_path_invalid")
        if not isinstance(payload, dict) or set(payload) != _PREVIEW_FIELDS:
            return _result(False, "execution_preview_payload_invalid")
        if (payload.get("operation") != "prepare_execution_preview"
                or payload.get("project_id") != project_id
                or payload.get("action") != ACTION_RUN_PYTHON
                or payload.get("scope") != SCOPE_EXECUTE
                or not validate_project_id(project_id)
                or not _valid_filename(payload.get("filename"))
                or not _valid_digest(payload.get("source_sha256"))
                or not isinstance(payload.get("resource_limits"), dict)):
            return _result(False, "execution_preview_payload_invalid")
        if payload["filename"] != os.path.basename(str(artifact_path)):
            return _result(False, "execution_artifact_binding_mismatch")

        context = _trusted_context(verified, project_id)
        proposal = self.ledger.prepare_execution_approval(
            trusted_context=context,
            project_id=project_id,
            authorized_code_root=authorized_code_root,
            artifact_path=artifact_path,
            verified_save=verified_save,
            resource_limits=payload["resource_limits"],
            expected_source_sha256=payload["source_sha256"],
            now=now,
        )
        if not proposal.get("ok"):
            return _result(False, proposal.get("reason"))

        preview = {
            "project_id": project_id,
            "filename": payload["filename"],
            "source_sha256": proposal["source_sha256"],
            "action": ACTION_RUN_PYTHON,
            "scope": SCOPE_EXECUTE,
            "resource_limits": dict(proposal["resource_limits"]),
            "network_policy": "none",
            "host_mounts": [],
            "approval_expires_at": proposal["expires_at"],
            "save_and_run_require_separate_approvals": True,
        }
        return _result(
            True,
            None,
            stage="execution_proposal_available",
            proposal_id=proposal["proposal_id"],
            capability_minted=False,
            preview=preview,
            executed=False,
        )

    def prepare_live_preview(
        self,
        *,
        proxy_secret,
        headers,
        payload,
        path,
        remote_addr,
        nonce_ledger,
        project_id,
        authorized_code_root,
        artifact_path,
        verified_save,
        now=None,
    ):
        """Prepare from a real signed UI action whose browser knows no digest."""
        verified = _verify_request(
            proxy_secret, headers, payload, path, remote_addr, now, nonce_ledger)
        if not verified.get("trusted"):
            return _result(False, verified.get("reason"))
        if path != PREVIEW_PATH:
            return _result(False, "execution_preview_path_invalid")
        if not isinstance(payload, dict) or set(payload) != _LIVE_PREVIEW_FIELDS:
            return _result(False, "execution_preview_payload_invalid")
        if (payload.get("operation") != "prepare_execution_preview"
                or payload.get("project_id") != project_id
                or not validate_project_id(project_id)
                or not _valid_filename(payload.get("filename"))
                or payload["filename"] != os.path.basename(str(artifact_path))):
            return _result(False, "execution_preview_payload_invalid")
        expected_digest = (verified_save or {}).get("digest")
        if not _valid_digest(expected_digest):
            return _result(False, "verified_save_evidence_required")
        context = _trusted_context(verified, project_id)
        proposal = self.ledger.prepare_execution_approval(
            trusted_context=context,
            project_id=project_id,
            authorized_code_root=authorized_code_root,
            artifact_path=artifact_path,
            verified_save=verified_save,
            resource_limits=dict(DEFAULT_RESOURCE_LIMITS),
            expected_source_sha256=expected_digest,
            now=now,
        )
        if not proposal.get("ok"):
            return _result(False, proposal.get("reason"))
        preview = {
            "project_id": project_id,
            "filename": payload["filename"],
            "source_sha256": proposal["source_sha256"],
            "action": ACTION_RUN_PYTHON,
            "scope": SCOPE_EXECUTE,
            "resource_limits": dict(proposal["resource_limits"]),
            "network_policy": "none",
            "host_mounts": [],
            "approval_expires_at": proposal["expires_at"],
            "save_and_run_require_separate_approvals": True,
        }
        return _result(
            True, None, stage="execution_proposal_available",
            proposal_id=proposal["proposal_id"], capability_minted=False,
            preview=preview, executed=False)

    def record_test_only_consent(
        self,
        *,
        proxy_secret,
        headers,
        payload,
        path,
        remote_addr,
        nonce_ledger,
        project_id,
        now=None,
        label=None,
        capability_ttl_seconds=MAX_CAPABILITY_TTL_SECONDS,
    ):
        if not self.test_mode or "TEST-ONLY" not in str(label or ""):
            return _result(False, "test_only_execution_consent_refused")
        verified = _verify_request(
            proxy_secret, headers, payload, path, remote_addr, now, nonce_ledger)
        if not verified.get("trusted"):
            return _result(False, verified.get("reason"))
        if path != CONSENT_PATH:
            return _result(False, "execution_consent_path_invalid")
        if not isinstance(payload, dict) or set(payload) != _CONSENT_FIELDS:
            return _result(False, "execution_consent_payload_invalid")
        if payload.get("project_id") != project_id:
            return _result(False, "execution_consent_project_mismatch")
        if (payload.get("operation") != "record_execution_consent"
                or payload.get("consent") is not True
                or payload.get("action") != ACTION_RUN_PYTHON
                or payload.get("scope") != SCOPE_EXECUTE
                or not validate_project_id(project_id)
                or not _valid_filename(payload.get("filename"))
                or not _valid_digest(payload.get("source_sha256"))
                or not isinstance(payload.get("proposal_id"), str)):
            return _result(False, "execution_consent_payload_invalid")

        status = self.ledger.inspect_status(payload["proposal_id"], now=now)
        if not status.get("ok"):
            return _result(False, status.get("reason"))
        if (status.get("project_id") != project_id
                or os.path.basename(str(status.get("artifact_path") or ""))
                != payload["filename"]
                or status.get("source_sha256") != payload["source_sha256"]
                or status.get("action") != payload["action"]
                or status.get("scope") != payload["scope"]):
            return _result(False, "execution_consent_binding_mismatch")

        context = _trusted_context(verified, project_id)
        event = self.ledger.record_test_only_approval_event(
            payload["proposal_id"], context, now=now, label=label)
        if not event.get("ok"):
            return _result(False, event.get("reason"))
        capability = self.ledger.mint_execution_capability(
            payload["proposal_id"],
            event["approval_event_id"],
            trusted_context=context,
            now=now,
            ttl_seconds=capability_ttl_seconds,
        )
        if not capability.get("ok"):
            return _result(False, capability.get("reason"))
        self._store_capability(capability, context)

        return _result(
            True,
            None,
            stage="execution_capability_minted",
            proposal_id=payload["proposal_id"],
            capability_id=capability["capability_id"],
            source_sha256=capability["source_sha256"],
            action=capability["action"],
            scope=capability["scope"],
            resource_limits=dict(capability["resource_limits"]),
            expires_at=capability["expires_at"],
            event_kind="TEST-ONLY",
            dispatch_performed=False,
            executed=False,
        )

    def record_trusted_local_consent(
        self,
        *,
        proxy_secret,
        headers,
        payload,
        path,
        remote_addr,
        nonce_ledger,
        project_id,
        now=None,
        capability_ttl_seconds=MAX_CAPABILITY_TTL_SECONDS,
    ):
        """Mint from a separately signed trusted-local UI action."""
        verified = _verify_request(
            proxy_secret, headers, payload, path, remote_addr, now, nonce_ledger)
        if not verified.get("trusted"):
            return _result(False, verified.get("reason"))
        if path != CONSENT_PATH:
            return _result(False, "execution_consent_path_invalid")
        if not isinstance(payload, dict) or set(payload) != _LIVE_CONSENT_FIELDS:
            return _result(False, "execution_consent_payload_invalid")
        if payload.get("project_id") != project_id:
            return _result(False, "execution_consent_project_mismatch")
        if (payload.get("operation") != "approve_and_run_python"
                or payload.get("consent") is not True
                or payload.get("action") != ACTION_RUN_PYTHON
                or payload.get("scope") != SCOPE_EXECUTE
                or not validate_project_id(project_id)
                or not _valid_filename(payload.get("filename"))
                or not _valid_digest(payload.get("source_sha256"))
                or not isinstance(payload.get("proposal_id"), str)):
            return _result(False, "execution_consent_payload_invalid")
        status = self.ledger.inspect_status(payload["proposal_id"], now=now)
        if not status.get("ok"):
            return _result(False, status.get("reason"))
        if (status.get("project_id") != project_id
                or os.path.basename(str(status.get("artifact_path") or ""))
                != payload["filename"]
                or status.get("source_sha256") != payload["source_sha256"]
                or status.get("action") != payload["action"]
                or status.get("scope") != payload["scope"]):
            return _result(False, "execution_consent_binding_mismatch")
        context = _trusted_context(verified, project_id)
        event = self.ledger._record_verified_approval_event(
            payload["proposal_id"], context, now=now,
            label="trusted local UI execution action",
            event_kind="TRUSTED_LOCAL_UI_ACTION",
            _verification_key=_VERIFIED_APPROVAL_EVENT_KEY,
        )
        if not event.get("ok"):
            return _result(False, event.get("reason"))
        capability = self.ledger.mint_execution_capability(
            payload["proposal_id"], event["approval_event_id"],
            trusted_context=context, now=now,
            ttl_seconds=capability_ttl_seconds,
        )
        if not capability.get("ok"):
            return _result(False, capability.get("reason"))
        self._store_capability(capability, context)
        return _result(
            True, None, stage="execution_capability_minted",
            proposal_id=payload["proposal_id"],
            capability_id=capability["capability_id"],
            source_sha256=capability["source_sha256"],
            action=capability["action"], scope=capability["scope"],
            resource_limits=dict(capability["resource_limits"]),
            expires_at=capability["expires_at"],
            event_kind="TRUSTED_LOCAL_UI_ACTION",
            dispatch_performed=False, executed=False)

    def authorization_for_dispatch(self, capability_id):
        """Internal server projection for the declarative execution gate."""
        with self._lock:
            binding = self._capability_bindings.get(capability_id)
            if not binding:
                return None
            context = binding["trusted_context"]
            return {
                "source": "user",
                "issuer": "server_capability_ledger",
                "scope": binding["scope"],
                "project_id": binding["project_id"],
                "session_id": context["session_id"],
                "source_sha256": binding["source_sha256"],
                "expires_at": binding["expires_at"],
                "consumed": False,
            }

    def claim_capability_for_dispatch(self, capability_id, *, now=None):
        """Consume a server-custodied capability; performs no dispatch."""
        with self._lock:
            token = self._capability_tokens.get(capability_id)
            binding = self._capability_bindings.get(capability_id)
        if token is None or not binding:
            return _result(False, "execution_capability_not_available")
        outcome = self.ledger.consume_execution_capability(
            capability_id=capability_id, token=token,
            trusted_context=binding["trusted_context"],
            project_id=binding["project_id"],
            artifact_path=binding["artifact_path"],
            source_sha256=binding["source_sha256"],
            action=binding["action"], scope=binding["scope"],
            resource_limits=binding["resource_limits"], now=now,
        )
        if outcome.get("ok") or outcome.get("reason") in {
            "execution_capability_consumed", "execution_capability_expired",
            "execution_capability_invalidated",
        }:
            with self._lock:
                self._capability_tokens.pop(capability_id, None)
                self._capability_bindings.pop(capability_id, None)
        if not outcome.get("ok"):
            return _result(False, outcome.get("reason"))
        return outcome

    def consume_test_only_capability(
        self,
        *,
        proxy_secret,
        headers,
        payload,
        path,
        remote_addr,
        nonce_ledger,
        project_id,
        artifact_path,
        now=None,
    ):
        """Atomically claim authority in offline tests; dispatch remains absent."""
        if not self.test_mode:
            return _result(False, "test_only_capability_claim_refused")
        verified = _verify_request(
            proxy_secret, headers, payload, path, remote_addr, now, nonce_ledger)
        if not verified.get("trusted"):
            return _result(False, verified.get("reason"))
        if path != CONSUME_PATH:
            return _result(False, "execution_claim_path_invalid")
        if not isinstance(payload, dict) or set(payload) != _CONSUME_FIELDS:
            return _result(False, "execution_claim_payload_invalid")
        if (payload.get("operation") != "consume_execution_capability"
                or payload.get("project_id") != project_id
                or payload.get("action") != ACTION_RUN_PYTHON
                or payload.get("scope") != SCOPE_EXECUTE
                or not validate_project_id(project_id)
                or not _valid_filename(payload.get("filename"))
                or not _valid_digest(payload.get("source_sha256"))
                or not isinstance(payload.get("capability_id"), str)
                or not isinstance(payload.get("resource_limits"), dict)):
            return _result(False, "execution_claim_payload_invalid")
        if payload["filename"] != os.path.basename(str(artifact_path)):
            return _result(False, "execution_artifact_binding_mismatch")

        with self._lock:
            token = self._capability_tokens.get(payload["capability_id"])
        if token is None:
            return _result(False, "execution_capability_not_available")
        context = _trusted_context(verified, project_id)
        outcome = self.ledger.consume_execution_capability(
            capability_id=payload["capability_id"],
            token=token,
            trusted_context=context,
            project_id=project_id,
            artifact_path=artifact_path,
            source_sha256=payload["source_sha256"],
            action=payload["action"],
            scope=payload["scope"],
            resource_limits=payload["resource_limits"],
            now=now,
        )
        if outcome.get("ok") or outcome.get("reason") in {
            "execution_capability_consumed",
            "execution_capability_expired",
            "execution_capability_invalidated",
        }:
            with self._lock:
                self._capability_tokens.pop(payload["capability_id"], None)
        if not outcome.get("ok"):
            return _result(False, outcome.get("reason"), executed=False)
        return _result(
            True,
            None,
            stage="execution_capability_consumed",
            capability_id=payload["capability_id"],
            filename=payload["filename"],
            source_sha256=payload["source_sha256"],
            action=ACTION_RUN_PYTHON,
            scope=SCOPE_EXECUTE,
            resource_limits=dict(payload["resource_limits"]),
            dispatch_performed=False,
            executed=False,
        )

    def inspect_status(self, record_id, now=None):
        status = self.ledger.inspect_status(record_id, now=now)
        if not status.get("ok"):
            return _result(False, status.get("reason"))
        return _result(
            True,
            None,
            record_type=status.get("record_type"),
            proposal_id=status.get("proposal_id"),
            capability_id=status.get("capability_id"),
            status=status.get("status"),
            capability_minted=status.get("capability_minted"),
            project_id=status.get("project_id"),
            filename=os.path.basename(str(status.get("artifact_path") or "")),
            source_sha256=status.get("source_sha256"),
            action=status.get("action"),
            scope=status.get("scope"),
            resource_limits=dict(status.get("resource_limits") or {}),
            expires_at=status.get("expires_at"),
            consumed=status.get("consumed"),
            invalidated=status.get("invalidated"),
        )

    def invalidate_all(self, reason="server_restart", now=None):
        result = self.ledger.invalidate_all(reason=reason, now=now)
        if result.get("ok"):
            with self._lock:
                self._capability_tokens.clear()
                self._capability_bindings.clear()
        return _result(
            bool(result.get("ok")), result.get("reason"),
            invalidated=result.get("invalidated", 0))


def describe_bridge():
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "trust_verifier": "existing_local_authorization_v1",
        "approval_event_kinds": ["TEST-ONLY"],
        "browser_route_registered": False,
        "live_chat_imported": False,
        "execution_enabled": False,
        "dispatch_available": False,
        "network_policy": "none",
        "host_mounts": [],
        "save_automatically_grants_execute": False,
    }
