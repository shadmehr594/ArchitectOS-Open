"""CODER-07B.2 §8 — execution contract hardening.

Pure tests. Nothing here touches Docker, Flask, a subprocess or the filesystem.
The contract is declarative by design and must stay that way: these tests prove
that the DECLARATIVE validation cannot be talked into accepting a request it has
no evidence for.

The five defects targeted, in the order they are checked:

  D1  a missing `now` silently skipped expiry, so an expired capability passed
  D2  a missing `bound_session_id` made the session check compare a value with
      itself, so any caller-authored session id passed
  D3  `authorization["source"] == "user"` is a self-description, not proof of
      who issued the capability
  D4  `backend_kind` is a self-description too: nothing evidenced that the
      isolation backend had ever been verified
  D5  file-save approval reused for execution (guard, already enforced)

`EXECUTION_ENABLED` must remain False throughout. This file asserts that too.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _path in (ROOT,):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from core.execution import execution_contract_v1 as ec  # noqa: E402

SOURCE = "def add(a, b):\n    return a + b\n"
DIGEST = ec.sha256_text(SOURCE)
NOW = 1_000_000.0
SESSION = "lss_server_bound_session"
PROJECT = "project_test"


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def valid_request(**overrides):
    request = {
        "project_id": PROJECT,
        "artifact_id": "documents/code/calculator.py",
        "source_sha256": DIGEST,
        "interpreter": "python3.12",
        "backend_kind": ec.BACKEND_RESTRICTED_CONTAINER,
        "network_policy": "none",
        "mounts": [],
        "privileged": False,
        "argv": [],
        "limits": {
            "max_runtime_seconds": 10,
            "max_memory_mb": 256,
            "max_cpus": 1.0,
            "max_output_bytes": 4096,
            "max_pids": 16,
        },
    }
    request.update(overrides)
    return request


def valid_authorization(**overrides):
    authorization = {
        "source": "user",
        "scope": ec.SCOPE_EXECUTE,
        "project_id": PROJECT,
        "session_id": SESSION,
        "source_sha256": DIGEST,
        "expires_at": NOW + 300,
        "consumed": False,
    }
    authorization.update(overrides)
    return authorization


def reason_for(request, authorization, **kwargs):
    kwargs.setdefault("source_text", SOURCE)
    kwargs.setdefault("now", NOW)
    kwargs.setdefault("bound_session_id", SESSION)
    return ec.validate_execution_request(request, authorization, **kwargs)


# ==========================================================
# THE SWITCH MUST STAY OFF
# ==========================================================

def test_execution_stays_disabled():
    check(ec.EXECUTION_ENABLED is False,
          "EXECUTION_ENABLED must remain False through CODER-07B.2")
    described = ec.describe_contract()
    check(described["executes_anything"] is False, "the contract must not claim execution")
    check(described["exposes_routes"] == [], "the contract must expose no routes")


# ==========================================================
# D1 — A MISSING TRUSTED CLOCK MUST REFUSE, NOT SKIP EXPIRY
# ==========================================================

def test_missing_trusted_time_cannot_skip_expiry():
    """RED: with now=None the expiry comparison was skipped entirely."""
    outcome = reason_for(
        valid_request(),
        valid_authorization(expires_at=NOW - 3600),
        now=None)

    check(outcome["allowed"] is False,
          "an expired capability must not pass because the caller omitted the "
          "current time; got allowed=%r" % (outcome["allowed"],))


def test_missing_trusted_time_is_reported_as_such():
    outcome = reason_for(
        valid_request(),
        valid_authorization(issuer=ec.APPROVAL_ISSUER_SERVER),
        now=None)
    check(outcome["allowed"] is False,
          "a request with no trusted clock must be refused, got %r" % (outcome["allowed"],))
    check(outcome["reason"] == ec.R_TRUSTED_TIME_REQUIRED,
          "expected %r, got %r" % (ec.R_TRUSTED_TIME_REQUIRED, outcome["reason"]))


def test_a_non_numeric_clock_is_refused():
    for bad in ("1000000", None, [], {}):
        outcome = reason_for(valid_request(), valid_authorization(), now=bad)
        check(outcome["allowed"] is False,
              "now=%r must not be accepted as a clock" % (bad,))


def test_a_bool_expiry_is_not_a_timestamp():
    """True is an int in Python; it must not pass as an expiry."""
    outcome = reason_for(valid_request(), valid_authorization(expires_at=True))
    check(outcome["allowed"] is False,
          "a boolean expiry must be refused, got %r" % (outcome["allowed"],))


# ==========================================================
# D2 — THE SESSION BINDING MUST COME FROM THE SERVER
# ==========================================================

def test_missing_server_session_binding_cannot_self_validate():
    """RED: bound_session_id=None made the comparison self-satisfying."""
    outcome = reason_for(
        valid_request(),
        valid_authorization(issuer=ec.APPROVAL_ISSUER_SERVER),
        bound_session_id=None)

    check(outcome["allowed"] is False,
          "a caller-authored session id must not validate against itself; "
          "got allowed=%r" % (outcome["allowed"],))
    check(outcome["reason"] == ec.R_SERVER_SESSION_REQUIRED,
          "expected %r, got %r" % (ec.R_SERVER_SESSION_REQUIRED, outcome["reason"]))


def test_a_caller_invented_session_is_refused_against_the_server_binding():
    outcome = reason_for(
        valid_request(),
        valid_authorization(session_id="lss_attacker_supplied",
                            issuer=ec.APPROVAL_ISSUER_SERVER),
        bound_session_id=SESSION)

    check(outcome["allowed"] is False, "a foreign session must be refused")
    check(outcome["reason"] == ec.R_SESSION_BINDING_MISMATCH,
          "expected %r, got %r" % (ec.R_SESSION_BINDING_MISMATCH, outcome["reason"]))


# ==========================================================
# D3 — PROVENANCE MUST BE ISSUER-BOUND, NOT SELF-DECLARED
# ==========================================================

def test_self_declared_user_source_is_not_proof_of_identity():
    """RED: `source: "user"` was accepted with no issuer binding at all."""
    outcome = reason_for(valid_request(), valid_authorization())

    check(outcome["allowed"] is False,
          "an authorization with no issuer binding must not be accepted as proof "
          "of who approved it; got allowed=%r" % (outcome["allowed"],))
    check(outcome["reason"] == ec.R_APPROVAL_PROVENANCE_UNVERIFIED,
          "expected %r, got %r" % (ec.R_APPROVAL_PROVENANCE_UNVERIFIED, outcome["reason"]))


def test_an_unknown_issuer_is_refused():
    outcome = reason_for(
        valid_request(), valid_authorization(issuer="the_model_itself"))
    check(outcome["allowed"] is False, "an unknown issuer must be refused")
    check(outcome["reason"] == ec.R_APPROVAL_PROVENANCE_UNVERIFIED,
          "expected %r, got %r" % (ec.R_APPROVAL_PROVENANCE_UNVERIFIED, outcome["reason"]))


def test_the_server_issuer_passes_provenance_and_reaches_the_next_requirement():
    """The issuer check is satisfiable; the evidence check is what stops it next."""
    outcome = reason_for(
        valid_request(), valid_authorization(issuer=ec.APPROVAL_ISSUER_SERVER))
    check(outcome["reason"] == ec.R_EXECUTION_CAPABILITY_UNVERIFIED,
          "with a valid issuer the next refusal must be the missing backend "
          "evidence, got %r" % (outcome["reason"],))


# ==========================================================
# D4 — AN UNVERIFIED BACKEND CAPABILITY MUST BE REFUSED
# ==========================================================

def test_a_backend_kind_alone_does_not_prove_the_backend_was_verified():
    """RED: `backend_kind` is a self-description with no evidence behind it."""
    outcome = reason_for(
        valid_request(), valid_authorization(issuer=ec.APPROVAL_ISSUER_SERVER))

    check(outcome["allowed"] is False,
          "claiming a backend class must not substitute for evidence that it was "
          "verified; got allowed=%r" % (outcome["allowed"],))
    check(outcome["reason"] == ec.R_EXECUTION_CAPABILITY_UNVERIFIED,
          "expected %r, got %r" % (ec.R_EXECUTION_CAPABILITY_UNVERIFIED, outcome["reason"]))


def test_a_weak_evidence_class_is_refused():
    for weak in ("source_inspection", "instantiation", "tested_offline", "partial", ""):
        outcome = reason_for(
            valid_request(backend_evidence=weak),
            valid_authorization(issuer=ec.APPROVAL_ISSUER_SERVER))
        check(outcome["allowed"] is False,
              "evidence class %r must not authorise execution" % (weak,))


def test_the_verified_evidence_class_is_accepted():
    outcome = reason_for(
        valid_request(backend_evidence=ec.BACKEND_EVIDENCE_VERIFIED),
        valid_authorization(issuer=ec.APPROVAL_ISSUER_SERVER))
    check(outcome["allowed"] is True, "the full contract must be satisfiable: %r" % (outcome,))


# ==========================================================
# D5 — FILE-SAVE APPROVAL CANNOT BE REUSED FOR EXECUTION
# ==========================================================

def test_save_and_overwrite_scopes_never_authorize_execution():
    for scope in (ec.SCOPE_SAVE, ec.SCOPE_OVERWRITE, "write", "approve", ""):
        outcome = reason_for(
            valid_request(backend_evidence=ec.BACKEND_EVIDENCE_VERIFIED),
            valid_authorization(scope=scope, issuer=ec.APPROVAL_ISSUER_SERVER))
        check(outcome["allowed"] is False,
              "scope %r must never authorise execution" % (scope,))
        check(outcome["reason"] == ec.R_EXECUTION_SCOPE_MISMATCH,
              "expected %r for scope %r, got %r"
              % (ec.R_EXECUTION_SCOPE_MISMATCH, scope, outcome["reason"]))


def test_authorize_execution_still_refuses_a_perfectly_valid_request():
    """The switch, not the validation, is what keeps execution off."""
    outcome = ec.authorize_execution(
        valid_request(backend_evidence=ec.BACKEND_EVIDENCE_VERIFIED),
        valid_authorization(issuer=ec.APPROVAL_ISSUER_SERVER),
        source_text=SOURCE, now=NOW, bound_session_id=SESSION)

    check(outcome["allowed"] is False,
          "authorize_execution must refuse while EXECUTION_ENABLED is False")
    check(outcome["reason"] == ec.R_EXECUTION_DISABLED,
          "expected %r, got %r" % (ec.R_EXECUTION_DISABLED, outcome["reason"]))
