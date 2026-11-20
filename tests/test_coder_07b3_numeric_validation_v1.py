"""CODER-07B.3 §1 — numeric validation, RED first.

The defect class: Python comparisons involving NaN return False, so a
"greater than the ceiling" guard is *not* a guard when the value is NaN. A value
must never pass merely because every comparison against it is False.

These tests are pure: no Docker, no engine, no filesystem, no subprocess. They
exercise the declarative contract and the adapter's spec validator directly.
"""

import math
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPPORT = os.path.join(ROOT, "tests", "support")
for _path in (ROOT, SUPPORT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from core.execution import execution_contract_v1 as ec  # noqa: E402
import bounded_docker_orchestrator_v1 as orch  # noqa: E402

SOURCE = "def add(a, b):\n    return a + b\n"
DIGEST = ec.sha256_text(SOURCE)
NOW = 1_000_000.0
SESSION = "lss_server_bound_session"
PROJECT = "project_test"

NAN = float("nan")
INF = float("inf")
NEG_INF = float("-inf")


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
        "backend_evidence": ec.BACKEND_EVIDENCE_VERIFIED,
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
        "issuer": ec.APPROVAL_ISSUER_SERVER,
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
# BASELINE — the contract still has a satisfiable path
# ==========================================================

def test_the_valid_request_still_validates():
    outcome = reason_for(valid_request(), valid_authorization())
    check(outcome["allowed"] is True, "baseline must pass, got %r" % (outcome,))


# ==========================================================
# §1a — THE CLOCK MUST BE A FINITE NUMBER
# ==========================================================

def test_nan_clock_does_not_bypass_expiry():
    """RED: nan > expires_at is False, so an expired capability passed."""
    outcome = reason_for(
        valid_request(), valid_authorization(expires_at=NOW - 3600), now=NAN)

    check(outcome["allowed"] is False,
          "a NaN clock must not bypass expiry; got allowed=%r reason=%r"
          % (outcome["allowed"], outcome["reason"]))


def test_negative_infinity_clock_does_not_bypass_expiry():
    """RED: -inf > expires_at is False, so expiry was skipped entirely."""
    outcome = reason_for(
        valid_request(), valid_authorization(expires_at=NOW - 3600), now=NEG_INF)

    check(outcome["allowed"] is False,
          "a -inf clock must not bypass expiry; got allowed=%r" % (outcome["allowed"],))


def test_positive_infinity_clock_is_refused_as_not_finite():
    outcome = reason_for(valid_request(), valid_authorization(), now=INF)
    check(outcome["allowed"] is False, "+inf is not a timestamp")


def test_nan_clock_is_reported_as_an_invalid_clock():
    outcome = reason_for(valid_request(), valid_authorization(), now=NAN)
    check(outcome["reason"] == ec.R_TRUSTED_TIME_INVALID,
          "expected %r, got %r" % (ec.R_TRUSTED_TIME_INVALID, outcome["reason"]))


# ==========================================================
# §1b — EXPIRY MUST BE A FINITE NUMBER
# ==========================================================

def test_nan_expiry_is_refused():
    """RED: a NaN expiry compares False, so it meant 'never expires'."""
    outcome = reason_for(valid_request(), valid_authorization(expires_at=NAN))

    check(outcome["allowed"] is False,
          "a NaN expiry must be refused; got allowed=%r" % (outcome["allowed"],))


def test_infinite_expiry_is_refused():
    for value in (INF, NEG_INF):
        outcome = reason_for(valid_request(), valid_authorization(expires_at=value))
        check(outcome["allowed"] is False,
              "expires_at=%r must be refused" % (value,))


def test_an_expiry_in_the_past_is_still_refused():
    outcome = reason_for(valid_request(), valid_authorization(expires_at=NOW - 1))
    check(outcome["reason"] == ec.R_EXECUTION_AUTHORIZATION_EXPIRED,
          "expected expired, got %r" % (outcome["reason"],))


def test_an_expiry_exactly_now_is_accepted_as_not_yet_expired():
    """Boundary: `now > expires_at` is the rule, so equal is not expired."""
    outcome = reason_for(valid_request(), valid_authorization(expires_at=NOW))
    check(outcome["allowed"] is True,
          "an expiry equal to now must not be treated as expired, got %r" % (outcome,))


# ==========================================================
# §1c — RESOURCE LIMITS MUST BE FINITE AND IN RANGE
# ==========================================================

@pytest.mark.parametrize("key", sorted(ec.LIMITS))
def test_nan_limit_is_refused_for_every_key(key):
    """RED: nan <= 0 and nan > ceiling are both False, so NaN passed."""
    limits = dict(valid_request()["limits"])
    limits[key] = NAN

    outcome = reason_for(valid_request(limits=limits), valid_authorization())

    check(outcome["allowed"] is False,
          "%s=nan must be refused; got allowed=%r" % (key, outcome["allowed"]))
    check(outcome["reason"] == ec.R_RESOURCE_LIMIT_INVALID,
          "%s=nan must report resource_limit_invalid, got %r"
          % (key, outcome["reason"]))


@pytest.mark.parametrize("key", sorted(ec.LIMITS))
def test_infinite_limit_is_refused_for_every_key(key):
    for value in (INF, NEG_INF):
        limits = dict(valid_request()["limits"])
        limits[key] = value
        outcome = reason_for(valid_request(limits=limits), valid_authorization())
        check(outcome["allowed"] is False,
              "%s=%r must be refused; got allowed=%r" % (key, value, outcome["allowed"]))


@pytest.mark.parametrize("key", sorted(ec.LIMITS))
def test_extreme_finite_limit_is_refused(key):
    limits = dict(valid_request()["limits"])
    limits[key] = 1e308
    outcome = reason_for(valid_request(limits=limits), valid_authorization())
    check(outcome["allowed"] is False,
          "%s=1e308 must be refused; got allowed=%r" % (key, outcome["allowed"]))


@pytest.mark.parametrize("key", sorted(ec.LIMITS))
def test_boolean_limit_is_refused(key):
    for value in (True, False):
        limits = dict(valid_request()["limits"])
        limits[key] = value
        outcome = reason_for(valid_request(limits=limits), valid_authorization())
        check(outcome["allowed"] is False,
              "%s=%r (a bool masquerading as a number) must be refused" % (key, value))


@pytest.mark.parametrize("key", sorted(ec.LIMITS))
def test_string_and_container_limits_are_refused(key):
    for value in ("10", b"10", [10], {"v": 10}, object()):
        limits = dict(valid_request()["limits"])
        limits[key] = value
        outcome = reason_for(valid_request(limits=limits), valid_authorization())
        check(outcome["allowed"] is False,
              "%s=%r must be refused; got allowed=%r"
              % (key, type(value).__name__, outcome["allowed"]))


def test_a_legal_limit_below_the_ceiling_is_accepted():
    limits = dict(valid_request()["limits"])
    limits["max_runtime_seconds"] = 1
    outcome = reason_for(valid_request(limits=limits), valid_authorization())
    check(outcome["allowed"] is True, "a legal limit must still pass: %r" % (outcome,))


def test_a_limit_exactly_at_the_ceiling_is_accepted():
    limits = dict(valid_request()["limits"])
    limits["max_runtime_seconds"] = ec.LIMITS["max_runtime_seconds"]
    outcome = reason_for(valid_request(limits=limits), valid_authorization())
    check(outcome["allowed"] is True,
          "a limit exactly at the ceiling is allowed (<=), got %r" % (outcome,))


def test_a_limit_one_above_the_ceiling_is_refused():
    limits = dict(valid_request()["limits"])
    limits["max_runtime_seconds"] = ec.LIMITS["max_runtime_seconds"] + 1
    outcome = reason_for(valid_request(limits=limits), valid_authorization())
    check(outcome["reason"] == ec.R_RESOURCE_LIMIT_INVALID,
          "one above the ceiling must be refused, got %r" % (outcome["reason"],))


# ==========================================================
# §1d — THE ADAPTER'S OWN SPEC VALIDATOR
# ==========================================================

@pytest.mark.parametrize("key", sorted(orch.LIMITS))
def test_orchestrator_refuses_nan_and_infinite_limits(key):
    """The chained comparison here is already NaN-safe; pinned so it stays so."""
    for value in (NAN, INF, NEG_INF):
        kwargs = {key: value}
        with pytest.raises(orch.OrchestrationRefused) as caught:
            orch.ContainerSpec("ubuntu-22.04", "echo_ok", **kwargs)
        check(caught.value.reason == orch.R_LIMIT_OUT_OF_BOUNDS,
              "%s=%r must be refused, got %r" % (key, value, caught.value.reason))


@pytest.mark.parametrize("key", sorted(orch.LIMITS))
def test_orchestrator_refuses_boolean_and_string_limits(key):
    for value in (True, "10", b"10", [1]):
        kwargs = {key: value}
        with pytest.raises(orch.OrchestrationRefused) as caught:
            orch.ContainerSpec("ubuntu-22.04", "echo_ok", **kwargs)
        check(caught.value.reason == orch.R_LIMIT_OUT_OF_BOUNDS,
              "%s=%r must be refused, got %r" % (key, value, caught.value.reason))


def test_orchestrator_accepts_a_legal_spec():
    spec = orch.ContainerSpec("ubuntu-22.04", "echo_ok")
    check(spec.deadline_seconds == 10.0, "default deadline must survive validation")


# ==========================================================
# §1e — THE FINITE-NUMBER PREDICATE ITSELF
# ==========================================================

def test_the_finite_number_predicate_exists_and_is_correct():
    check(hasattr(ec, "is_finite_number"),
          "the contract must expose a single finite-number predicate")

    for good in (0, 1, -1, 1.5, 0.0, 1e308, -1e308, 10 ** 30):
        check(ec.is_finite_number(good), "%r must count as finite" % (good,))

    for bad in (NAN, INF, NEG_INF, True, False, "1", None, [], {}, object()):
        check(not ec.is_finite_number(bad),
              "%r must NOT count as a finite number" % (bad,))
