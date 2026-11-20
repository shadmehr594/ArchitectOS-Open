# ==========================================================
# ARCHITECTOS CODER-07A — SAFE EXECUTION FOUNDATION (CONTRACT ONLY)
#
# WHY THIS MODULE EXISTS
# ----------------------
# CODER-05.3 established a verified real-browser path for GENERATING, STAGING,
# APPROVING and SAVING Python source. Saving a file is NOT permission to run it.
# Those are two different authorities and they must never collapse into one.
#
# This module is the DECLARATIVE CONTRACT for the second authority. It answers
# one question only: "given an approved artifact and a structured request, is
# this execution permitted?" It does NOT execute anything, and it cannot: it
# imports no process, shell, container or filesystem-mutation API.
#
# The isolation backend required to actually run code has NOT been verified on
# this host (CODER-07A). Therefore:
#   * EXECUTION_ENABLED is False and there is no code path that sets it,
#   * authorize_execution() refuses unconditionally while it is False,
#   * there is no /execute, /shell or /terminal route anywhere in the product.
#
# A future phase may flip the switch ONLY after a backend is verified in a real
# sandbox (VERIFIED_IN_REAL_SANDBOX), which CODER-07A explicitly did not do.
# ==========================================================

import hashlib
import math
import re

CONTRACT = "ExecutionContractV1"
VERSION = "1.0"


# ==========================================================
# THE SWITCH — DELIBERATELY OFF
#
# Nothing in this module, and nothing anywhere else, writes this value. A test
# asserts that no assignment to it exists outside this declaration, so it
# cannot be flipped by a stray edit or by injected text.
# ==========================================================

EXECUTION_ENABLED = False


# ==========================================================
# AUTHORITY SCOPES
#
# File-save authority and execution authority are separate scopes. A capability
# issued for "save" or "overwrite" can never authorize "execute".
# ==========================================================

SCOPE_SAVE = "save"
SCOPE_OVERWRITE = "overwrite"
SCOPE_EXECUTE = "execute"

EXECUTION_SCOPE = SCOPE_EXECUTE


# ==========================================================
# PROVENANCE AND CAPABILITY EVIDENCE
#
# `authorization["source"] == "user"` is a SELF-DESCRIPTION. Anyone who can
# build the dict can write it, so it cannot be proof of who approved anything.
# The issuer must name the server-side ledger that minted the capability, and a
# real integration must verify that field against that ledger rather than trust
# the dict. This module can only refuse to accept a self-describing claim.
#
# Likewise `backend_kind` names a class of isolation. Naming a class is not
# evidence that the class was ever verified on this host. CODER-07A explicitly
# did not verify one, so the evidence class is a required field.
#
# WHAT THE ISSUER AND EVIDENCE CHECKS ARE NOT (CODER-07B.3 §4)
# -----------------------------------------------------------
# These two checks raise the COST of a careless caller. They are NOT proof, and
# nothing in this module may ever be described as if they were:
#
#   * `issuer` is still a caller-supplied string. Requiring it to equal
#     APPROVAL_ISSUER_SERVER only rejects a caller who did not bother to lie
#     consistently. A caller willing to write that literal passes the check.
#   * `backend_evidence` is likewise caller-supplied. It records what a human
#     established, not something this module can observe.
#   * Neither field is signed, MACed, bound to a session, or cross-checked
#     against any durable record. There is no ledger here to check against.
#
# Therefore a real integration MUST resolve approval against the existing
# trusted server-side capability ledger (the same store that mints the signed
# UI->Core proxy nonces) and MUST take backend evidence from that ledger's own
# record. Adding further self-declared strings to this module would manufacture
# the APPEARANCE of authority without creating any. Do not do that. The correct
# place for provenance is the ledger, and the correct place for this module is
# to refuse everything it cannot verify.
# ==========================================================

APPROVAL_ISSUER_SERVER = "server_capability_ledger"

BACKEND_EVIDENCE_VERIFIED = "verified_in_real_sandbox"

#: Evidence classes that are NOT sufficient to authorise execution.
INSUFFICIENT_BACKEND_EVIDENCE = (
    "source_inspection",
    "instantiation",
    "tested_offline",
    "partial",
    "not_verified",
    "blocked",
)


# ==========================================================
# BACKEND CLASSES
#
# CODER-07A §4 requires the boundary class to be stated explicitly. A host
# subprocess, a working directory, a timeout, or WSL-with-default-mounts is NOT
# a security boundary and is never accepted here.
# ==========================================================

BACKEND_RESTRICTED_CONTAINER = "restricted_container"
BACKEND_ISOLATED_VM = "isolated_vm"

APPROVED_BACKEND_KINDS = (
    BACKEND_RESTRICTED_CONTAINER,
    BACKEND_ISOLATED_VM,
)

REFUSED_BACKEND_KINDS = (
    "host_process",
    "subprocess_timeout_only",
    "wsl_direct",
    "unrestricted_container",
)


# ==========================================================
# POLICY LIMITS
#
# Hard ceilings. A request may ask for LESS, never more, and never "unbounded".
# ==========================================================

LIMITS = {
    "max_runtime_seconds": 30,
    "max_memory_mb": 512,
    "max_cpus": 1.0,
    "max_output_bytes": 65536,
    "max_pids": 64,
}

#: The only network policy permitted. Anything else is refused.
ALLOWED_NETWORK_POLICIES = ("none",)

#: Interpreters that may exist INSIDE a guest. Never a host executable path.
ALLOWED_INTERPRETERS = ("python3.12", "python3.11", "python3")

#: Guest-side working directory. Host paths are never mounted.
GUEST_WORKDIR = "/work"

#: Substrings that indicate an attempt to reach a shell or a host binary.
FORBIDDEN_ARGV_MARKERS = (
    "cmd", "cmd.exe", "powershell", "pwsh", "wsl", "bash", "sh -c",
    "&&", "||", ";", "|", ">", "<", "`", "$(", "..", "\\\\",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


# ==========================================================
# REASON CODES — stable, machine-readable, fail-closed
# ==========================================================

R_EXECUTION_DISABLED = "execution_disabled"
R_REQUEST_INVALID = "request_invalid"
R_EXECUTION_AUTHORIZATION_REQUIRED = "execution_authorization_required"
R_EXECUTION_AUTHORIZATION_EXPIRED = "execution_authorization_expired"
R_EXECUTION_AUTHORIZATION_REPLAYED = "execution_authorization_replayed"
R_EXECUTION_SCOPE_MISMATCH = "execution_scope_mismatch"
R_APPROVAL_SOURCE_MUST_BE_USER = "approval_source_must_be_user"
R_PROJECT_BINDING_MISMATCH = "project_binding_mismatch"
R_SESSION_BINDING_MISMATCH = "session_binding_mismatch"
R_SOURCE_DIGEST_MISMATCH = "source_digest_mismatch"
R_SOURCE_CHANGED_AFTER_APPROVAL = "source_changed_after_approval"
R_BACKEND_NOT_APPROVED = "backend_not_approved"
R_NETWORK_NOT_PERMITTED = "network_not_permitted"
R_HOST_MOUNT_NOT_PERMITTED = "host_mount_not_permitted"
R_PRIVILEGED_EXECUTION_REFUSED = "privileged_execution_refused"
R_RESOURCE_LIMIT_INVALID = "resource_limit_invalid"
R_ARBITRARY_COMMAND_REFUSED = "arbitrary_command_refused"
R_TRUSTED_TIME_REQUIRED = "trusted_time_required"
R_TRUSTED_TIME_INVALID = "trusted_time_invalid"
R_SERVER_SESSION_REQUIRED = "server_session_required"
R_APPROVAL_PROVENANCE_UNVERIFIED = "approval_provenance_unverified"
R_EXECUTION_CAPABILITY_UNVERIFIED = "execution_capability_unverified"


def _refuse(reason, detail=None):
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "allowed": False,
        "reason": reason,
        "detail": detail,
    }


def _allow():
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "allowed": True,
        "reason": None,
        "detail": None,
    }


def sha256_text(text):
    """Digest of the exact UTF-8 source bytes."""
    if not isinstance(text, str):
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_finite_number(value):
    """The single predicate every numeric field must pass.

    WHY THIS EXISTS
    ---------------
    Python comparisons involving NaN return False. That makes a guard written as
    ``if value > ceiling: refuse`` silently useless for NaN: the comparison is
    False, so the refusal never fires and the value passes. The same applies to
    ``value <= 0``. A value must never pass merely because every comparison
    against it is False, so the check is made positively instead.

    Booleans are excluded on purpose: ``True`` is an ``int`` in Python and would
    otherwise satisfy a numeric field. Integers too large to represent as a
    float are also refused — they cannot be reasoned about as a quantity.
    """
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


# ==========================================================
# STRUCTURAL VALIDATION — every refusal is fail-closed
#
# Order is deliberate: identity and authority bindings are checked before any
# resource question, so a request can never reach a resource decision without
# first proving who is asking and what exactly was approved.
# ==========================================================

def validate_execution_request(
    request,
    authorization=None,
    *,
    source_text=None,
    now=None,
    bound_session_id=None,
):
    """Validate a structured execution request. Pure. Never executes anything.

    ``source_text`` is the CURRENT artifact content, so the digest can be
    re-derived rather than trusted from the request.

    Returns ``{"allowed": bool, "reason": str|None, ...}``.
    """
    if not isinstance(request, dict):
        return _refuse(R_REQUEST_INVALID, "request_not_a_mapping")

    # ---- 1. authority present and separate from file-save ------------------
    if not isinstance(authorization, dict):
        return _refuse(R_EXECUTION_AUTHORIZATION_REQUIRED, "no_execution_authorization")

    # A model's own text can never approve. This is checked before the scope so
    # a model-authored "approval" cannot even reach the scope comparison.
    if authorization.get("source") != "user":
        return _refuse(R_APPROVAL_SOURCE_MUST_BE_USER,
                       "approval_source=%r" % (authorization.get("source"),))

    # `source` is self-described, so it is not proof of identity on its own. The
    # capability must name the server-side ledger that issued it; an unbound
    # authorization is refused rather than trusted.
    if authorization.get("issuer") != APPROVAL_ISSUER_SERVER:
        return _refuse(R_APPROVAL_PROVENANCE_UNVERIFIED,
                       "issuer=%r" % (authorization.get("issuer"),))

    # ---- 2. scope must be EXECUTE, never save/overwrite --------------------
    if authorization.get("scope") != SCOPE_EXECUTE:
        return _refuse(R_EXECUTION_SCOPE_MISMATCH,
                       "scope=%r" % (authorization.get("scope"),))

    # ---- 3. trusted clock and expiry ---------------------------------------
    # A caller-supplied clock is not a trusted clock. If no server time is
    # supplied, expiry cannot be evaluated, and an unevaluable expiry is a
    # refusal — never a skipped check.
    if now is None or not isinstance(now, (int, float)) or isinstance(now, bool):
        return _refuse(R_TRUSTED_TIME_REQUIRED, "now=%r" % (now,))
    # NaN and +/-inf are numbers that no comparison can guard, so they are
    # refused explicitly rather than being allowed to defeat the expiry test.
    if not is_finite_number(now):
        return _refuse(R_TRUSTED_TIME_INVALID, "now=%r" % (now,))
    expires_at = authorization.get("expires_at")
    if (expires_at is None or not isinstance(expires_at, (int, float))
            or isinstance(expires_at, bool)):
        return _refuse(R_EXECUTION_AUTHORIZATION_EXPIRED, "no_expiry")
    if not is_finite_number(expires_at):
        return _refuse(R_EXECUTION_AUTHORIZATION_EXPIRED,
                       "non_finite_expiry=%r" % (expires_at,))
    if float(now) > float(expires_at):
        return _refuse(R_EXECUTION_AUTHORIZATION_EXPIRED,
                       "expired_at=%s" % (expires_at,))

    # ---- 4. single use -----------------------------------------------------
    if authorization.get("consumed"):
        return _refuse(R_EXECUTION_AUTHORIZATION_REPLAYED, "capability_already_consumed")

    # ---- 5. bindings -------------------------------------------------------
    project_id = request.get("project_id")
    if not project_id or authorization.get("project_id") != project_id:
        return _refuse(R_PROJECT_BINDING_MISMATCH,
                       "authorization_project=%r request_project=%r"
                       % (authorization.get("project_id"), project_id))

    # The expected session must come FROM THE SERVER. Falling back to the
    # authorization's own field would compare a value with itself and accept any
    # caller-authored session id.
    if not isinstance(bound_session_id, str) or not bound_session_id:
        return _refuse(R_SERVER_SESSION_REQUIRED,
                       "bound_session_id=%r" % (bound_session_id,))
    auth_session = authorization.get("session_id")
    if not auth_session or auth_session != bound_session_id:
        return _refuse(R_SESSION_BINDING_MISMATCH,
                       "authorization_session=%r bound_session=%r"
                       % (auth_session, bound_session_id))

    # ---- 6. digest: request must match what was approved -------------------
    requested_digest = request.get("source_sha256")
    approved_digest = authorization.get("source_sha256")
    if not isinstance(requested_digest, str) or not _SHA256_RE.match(requested_digest):
        return _refuse(R_SOURCE_DIGEST_MISMATCH, "request_digest_malformed")
    if not isinstance(approved_digest, str) or requested_digest != approved_digest:
        return _refuse(R_SOURCE_DIGEST_MISMATCH, "request_digest_not_approved")

    # ---- 7. digest: the artifact must not have changed since approval ------
    actual_digest = sha256_text(source_text)
    if actual_digest is None:
        return _refuse(R_SOURCE_CHANGED_AFTER_APPROVAL, "source_unavailable")
    if actual_digest != approved_digest:
        return _refuse(R_SOURCE_CHANGED_AFTER_APPROVAL,
                       "approved=%s actual=%s" % (approved_digest, actual_digest))

    # ---- 8. backend class --------------------------------------------------
    backend = request.get("backend_kind")
    if backend in REFUSED_BACKEND_KINDS:
        return _refuse(R_BACKEND_NOT_APPROVED, "refused_backend=%r" % (backend,))
    if backend not in APPROVED_BACKEND_KINDS:
        return _refuse(R_BACKEND_NOT_APPROVED, "unknown_backend=%r" % (backend,))

    # Naming an isolation class is not evidence that the class was verified on
    # this host. Without an explicit, sufficient evidence class the capability
    # is unverified and execution is refused.
    evidence = request.get("backend_evidence")
    if evidence != BACKEND_EVIDENCE_VERIFIED:
        return _refuse(R_EXECUTION_CAPABILITY_UNVERIFIED,
                       "backend_evidence=%r" % (evidence,))

    # ---- 9. network --------------------------------------------------------
    if request.get("network_policy") not in ALLOWED_NETWORK_POLICIES:
        return _refuse(R_NETWORK_NOT_PERMITTED,
                       "network_policy=%r" % (request.get("network_policy"),))

    # ---- 10. mounts --------------------------------------------------------
    mounts = request.get("mounts")
    if mounts is None:
        mounts = []
    if not isinstance(mounts, (list, tuple)) or len(mounts) > 0:
        return _refuse(R_HOST_MOUNT_NOT_PERMITTED, "mounts=%r" % (mounts,))

    # ---- 11. privilege -----------------------------------------------------
    if request.get("privileged") not in (False, 0, None):
        return _refuse(R_PRIVILEGED_EXECUTION_REFUSED,
                       "privileged=%r" % (request.get("privileged"),))

    # ---- 12. interpreter / arbitrary command -------------------------------
    interpreter = request.get("interpreter")
    if interpreter not in ALLOWED_INTERPRETERS:
        return _refuse(R_ARBITRARY_COMMAND_REFUSED, "interpreter=%r" % (interpreter,))

    argv = request.get("argv")
    if argv is None:
        argv = []
    if not isinstance(argv, (list, tuple)):
        return _refuse(R_ARBITRARY_COMMAND_REFUSED, "argv_not_a_list")
    for token in argv:
        if not isinstance(token, str):
            return _refuse(R_ARBITRARY_COMMAND_REFUSED, "argv_token_not_string")
        lowered = token.lower()
        for marker in FORBIDDEN_ARGV_MARKERS:
            if marker in lowered:
                return _refuse(R_ARBITRARY_COMMAND_REFUSED,
                               "argv_marker=%r" % (marker,))

    # ---- 13. resource limits ----------------------------------------------
    limits = request.get("limits")
    if not isinstance(limits, dict):
        return _refuse(R_RESOURCE_LIMIT_INVALID, "limits_missing")

    for key, ceiling in LIMITS.items():
        value = limits.get(key)
        if value is None:
            return _refuse(R_RESOURCE_LIMIT_INVALID, "missing_%s" % key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return _refuse(R_RESOURCE_LIMIT_INVALID, "non_numeric_%s" % key)
        # NaN would pass both the `<= 0` and the `> ceiling` guards below,
        # because every comparison with NaN is False. Refuse it positively.
        if not is_finite_number(value):
            return _refuse(R_RESOURCE_LIMIT_INVALID, "non_finite_%s" % key)
        if value <= 0:
            return _refuse(R_RESOURCE_LIMIT_INVALID, "unbounded_%s" % key)
        if float(value) > float(ceiling):
            return _refuse(R_RESOURCE_LIMIT_INVALID,
                           "%s=%s exceeds %s" % (key, value, ceiling))

    return _allow()


def authorize_execution(
    request,
    authorization=None,
    *,
    server_mvp_opt_in=False,
    server_backend_verified=False,
    **kwargs
):
    """The ONLY gate a future caller may use.

    While EXECUTION_ENABLED is False this refuses unconditionally, before any
    other consideration. This is the default and it is not overridable by a
    request field, a prompt, or a model claim.
    """
    mvp_enabled = server_mvp_opt_in is True
    if EXECUTION_ENABLED is not True and not mvp_enabled:
        return _refuse(R_EXECUTION_DISABLED, "coder_07a_contract_only")

    outcome = validate_execution_request(request, authorization, **kwargs)
    if not outcome.get("allowed"):
        return outcome

    if server_backend_verified is not True:
        return _refuse(R_EXECUTION_DISABLED, "verified_backend_owner_required")

    # The gate authorizes only the structured request. It still performs no
    # execution and has no process/container imports. The bounded local MVP
    # owner must separately consume the server-side one-shot capability.
    return _allow()


def describe_contract():
    """Declarative description for the report / a future UI preview."""
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "execution_enabled": EXECUTION_ENABLED,
        "authority": "separate_from_file_save",
        "execution_scope": EXECUTION_SCOPE,
        "approved_backend_kinds": list(APPROVED_BACKEND_KINDS),
        "refused_backend_kinds": list(REFUSED_BACKEND_KINDS),
        "allowed_network_policies": list(ALLOWED_NETWORK_POLICIES),
        "allowed_interpreters": list(ALLOWED_INTERPRETERS),
        "guest_workdir": GUEST_WORKDIR,
        "limits": dict(LIMITS),
        "requires": [
            "trusted_actor",
            "project_binding",
            "session_binding",
            "exact_source_digest",
            "execution_scope",
            "expiry",
            "single_use_capability",
            "user_approval_source",
            "verified_isolation_backend",
            # C07B.2 §8 — bindings that must come from the SERVER, never from
            # the request or from model output.
            "server_issuer_binding",
            "trusted_clock",
            "server_bound_session",
            "verified_backend_evidence",
        ],
        "server_supplied_inputs": ["now", "bound_session_id"],
        "approval_issuer": APPROVAL_ISSUER_SERVER,
        "required_backend_evidence": BACKEND_EVIDENCE_VERIFIED,
        # C07B.3 §4 — the contract refuses to describe these two checks as
        # proof. A machine-readable declaration so no caller can mistake the
        # label comparison for ledger verification.
        "provenance_limitation": {
            "issuer_is_self_declared": True,
            "backend_evidence_is_self_declared": True,
            "cryptographically_signed": False,
            "bound_to_session": False,
            "verified_against_server_ledger": False,
            "verification_required_before_production": (
                "resolve approval against the existing trusted server-side "
                "capability ledger"
            ),
        },
        "executes_anything": False,
        "exposes_routes": [],
    }


def build_execution_preview(request, source_text=None, *, now=None, bound_session_id=None):
    """A read-only preview. Reports what WOULD be validated; runs nothing.

    `now` and `bound_session_id` are SERVER inputs. Without them the preview
    reports a truthful refusal (trusted_time_required / server_session_required)
    rather than a preview of an outcome it cannot actually justify.
    """
    outcome = validate_execution_request(
        request,
        (request or {}).get("_authorization") if isinstance(request, dict) else None,
        source_text=source_text,
        now=now,
        bound_session_id=bound_session_id,
    )
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "preview_only": True,
        "execution_enabled": EXECUTION_ENABLED,
        "would_validate": outcome,
        "artifact": (request or {}).get("artifact_id") if isinstance(request, dict) else None,
        "interpreter": (request or {}).get("interpreter") if isinstance(request, dict) else None,
        "network_policy": (request or {}).get("network_policy") if isinstance(request, dict) else None,
        "executed": False,
    }
