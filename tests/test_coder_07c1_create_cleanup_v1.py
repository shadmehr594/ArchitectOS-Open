# ==========================================================
# ARCHITECTOS CODER-07C.1 — §2 DEFECT A: NONZERO `docker create`
#
# CODER-07C.0 demonstrated that a nonzero `docker create` returncode raises
# without attempting exact-name cleanup and without recording a possible
# orphan. `docker create` prints the id only AFTER the daemon has committed the
# container, so a nonzero exit can still mean a container exists: a failed
# stdout write, a killed CLI, or a lost response all produce that shape.
#
# The two adjacent failure paths — create timeout and unparseable id — both
# call `_remove_unidentified(name)`. This suite requires the third path to do
# the same, and requires every unproven outcome to be recorded as a liability
# that blocks the next run.
#
# NO DOCKER CONTACT. `_run_docker` is replaced in-process, so no daemon is
# reached and no container can exist. These are pure tests.
# ==========================================================

import os
import subprocess
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SUPPORT = os.path.join(_ROOT, "tests", "support")
for _path in (_ROOT, _SUPPORT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import bounded_docker_orchestrator_v1 as orch  # noqa: E402


# ----------------------------------------------------------
# Harness
# ----------------------------------------------------------

def completed(returncode, stdout=b"", stderr=b""):
    return subprocess.CompletedProcess(
        args=["docker"], returncode=returncode, stdout=stdout, stderr=stderr)


class FakeDocker:
    """Scripted docker CLI. Records every invocation; executes nothing."""

    def __init__(self, create=None, rm=None, inspect=None):
        self.calls = []
        self._create = create if create is not None else completed(0)
        self._rm = rm if rm is not None else completed(0)
        self._inspect = inspect if inspect is not None else completed(
            1, b"", b"Error: No such object: c07b1-deadbeef")

    def __call__(self, args, timeout=10800):
        self.calls.append(list(args))
        verb = args[0] if args else ""
        if verb == "ps":
            return completed(0, b"", b"")
        if verb == "create":
            if isinstance(self._create, BaseException):
                raise self._create
            return self._create
        if verb == "rm":
            if isinstance(self._rm, BaseException):
                raise self._rm
            return self._rm
        if verb == "inspect":
            if isinstance(self._inspect, BaseException):
                raise self._inspect
            return self._inspect
        return completed(0, b"", b"")

    def verbs(self):
        return [call[0] for call in self.calls]

    def cleanup_calls(self):
        return [call for call in self.calls if call and call[0] in ("rm", "stop", "kill")]

    def cleanup_used_a_prefix_or_filter(self):
        """Cleanup must target ONE exact reference, never a pattern."""
        for call in self.cleanup_calls():
            for token in call[1:]:
                if any(ch in token for ch in ("*", "?", "=", "|")):
                    return True
        return False


def build(fake):
    instance = orch.BoundedDockerOrchestrator()
    instance._run_docker = fake
    return instance


def run_once(instance, deadline=5):
    try:
        instance.run(orch.ContainerSpec("ubuntu-22.04", "echo_ok",
                                        deadline_seconds=deadline))
    except orch.OrchestrationRefused as exc:
        return exc
    raise AssertionError("expected OrchestrationRefused")


# ----------------------------------------------------------
# A1 — the defect itself: cleanup must be attempted
# ----------------------------------------------------------

def test_a_nonzero_create_attempts_exact_name_cleanup():
    """RED before the fix: the nonzero-create path performed no cleanup."""
    fake = FakeDocker(create=completed(1, b"", b"Error response from daemon: boom"))
    instance = build(fake)

    refused = run_once(instance)

    assert refused.reason == orch.R_CREATE_FAILED
    assert fake.cleanup_calls(), (
        "a nonzero create must attempt cleanup: the adapter cannot know that "
        "nothing was created. verbs=%r" % (fake.verbs(),))


def test_a_cleanup_targets_one_exact_name_and_never_a_pattern():
    fake = FakeDocker(create=completed(1, b"", b"Error response from daemon: boom"))
    instance = build(fake)

    run_once(instance)

    assert fake.cleanup_calls(), "cleanup must be attempted"
    assert not fake.cleanup_used_a_prefix_or_filter(), (
        "cleanup must use one exact reference: %r" % (fake.cleanup_calls(),))

    # The reference is the exact generated container name, not a uuid prefix
    # and not a filter expression.
    reference = fake.cleanup_calls()[0][-1]
    assert reference.startswith(orch.NAME_PREFIX)
    assert len(reference) == len(orch.NAME_PREFIX) + 12


# ----------------------------------------------------------
# A2 — confirmed absence clears the liability
# ----------------------------------------------------------

def test_a_confirmed_absence_records_no_liability():
    fake = FakeDocker(
        create=completed(1, b"", b"Error response from daemon: boom"),
        rm=completed(0, b"", b""),
        inspect=completed(1, b"", b"Error: No such object: gone"),
    )
    instance = build(fake)

    run_once(instance)

    assert instance.unresolved_liabilities() == [], (
        "a confirmed absence must not be recorded as a liability")


def test_a_second_absence_marker_is_also_accepted():
    fake = FakeDocker(
        create=completed(1, b"", b"boom"),
        rm=completed(0),
        inspect=completed(1, b"", b"Error: No such container: gone"),
    )
    instance = build(fake)

    run_once(instance)

    assert instance.unresolved_liabilities() == []


# ----------------------------------------------------------
# A3 — still present, daemon unreachable, permission denied
# ----------------------------------------------------------

@pytest.mark.parametrize("label,inspect", [
    ("still_present", completed(0, b"abc123", b"")),
    ("daemon_unreachable", completed(
        1, b"", b"error during connect: cannot connect to the Docker daemon")),
    ("permission_denied", completed(
        1, b"", b"permission denied while trying to connect to the docker API")),
    ("unexpected_api_error", completed(1, b"", b"Error: something unexpected happened")),
])
def test_a_unproven_absence_is_recorded_as_a_liability(label, inspect):
    fake = FakeDocker(
        create=completed(1, b"", b"Error response from daemon: boom"),
        rm=completed(1, b"", b"Error response from daemon: cannot remove"),
        inspect=inspect,
    )
    instance = build(fake)

    run_once(instance)

    assert instance.unresolved_liabilities(), (
        "%s must leave the name in unresolved liabilities" % label)


def test_a_nonzero_inspect_alone_never_claims_removal():
    """'cannot tell' must never be reported as 'removed'."""
    fake = FakeDocker(
        create=completed(1, b"", b"boom"),
        rm=completed(1, b"", b"cannot remove"),
        inspect=completed(1, b"", b"error during connect: cannot connect"),
    )
    instance = build(fake)

    run_once(instance)

    assert instance._removed_ids == [], (
        "an unverified reference must never enter the removed ledger")


# ----------------------------------------------------------
# A4 — the original error and the cleanup outcome stay independent
# ----------------------------------------------------------

def test_a_original_error_and_cleanup_outcome_are_reported_separately():
    fake = FakeDocker(
        create=completed(1, b"", b"Error response from daemon: original-cause"),
        rm=completed(1, b"", b"cannot remove"),
        inspect=completed(1, b"", b"error during connect: cannot connect"),
    )
    instance = build(fake)

    refused = run_once(instance)

    # The create failure must survive in the detail ...
    assert "original-cause" in refused.detail, (
        "the original create error must be preserved: %r" % (refused.detail,))
    # ... and the cleanup outcome must be present as a distinct statement.
    assert "cleanup=" in refused.detail, (
        "the cleanup outcome must be reported separately: %r" % (refused.detail,))
    assert orch.REMOVAL_UNVERIFIED in refused.detail


# ----------------------------------------------------------
# A5 — the timeout path keeps working (contrast, not the defect)
# ----------------------------------------------------------

def test_a_create_timeout_still_cleans_up():
    fake = FakeDocker(
        create=subprocess.TimeoutExpired(cmd="docker", timeout=10800),
        rm=completed(0),
        inspect=completed(1, b"", b"Error: No such object"),
    )
    instance = build(fake)

    run_once(instance)

    assert fake.cleanup_calls(), "the timeout path must still attempt cleanup"


# ----------------------------------------------------------
# A6 — a liability blocks the next run
# ----------------------------------------------------------

def test_a_pending_liability_refuses_the_next_run():
    fake = FakeDocker(
        create=completed(1, b"", b"boom"),
        rm=completed(1, b"", b"cannot remove"),
        inspect=completed(1, b"", b"error during connect: cannot connect"),
    )
    instance = build(fake)

    run_once(instance)
    assert instance.unresolved_liabilities()

    # The second run must refuse BEFORE touching docker at all.
    before = len(fake.calls)
    refused = run_once(instance)

    assert refused.reason == orch.R_UNRESOLVED_CLEANUP
    assert len(fake.calls) == before, (
        "a refused run must not contact the engine: %r"
        % (fake.calls[before:],))


def test_a_liability_is_reported_with_its_exact_reference():
    fake = FakeDocker(
        create=completed(1, b"", b"boom"),
        rm=completed(1),
        inspect=completed(1, b"", b"cannot connect"),
    )
    instance = build(fake)

    run_once(instance)

    liabilities = instance.unresolved_liabilities()
    assert len(liabilities) == 1
    assert liabilities[0].startswith(orch.NAME_PREFIX)


# ----------------------------------------------------------
# A7 — no container is ever created by this suite
# ----------------------------------------------------------

def test_a_the_suite_never_reaches_a_real_engine():
    """Guard against a future edit that removes the injection seam."""
    fake = FakeDocker(create=completed(1, b"", b"boom"))
    instance = build(fake)

    run_once(instance)

    assert fake.calls, "the fake must have been used"
    assert all(call and call[0] in ("ps", "create", "rm", "inspect", "stop", "kill")
               for call in fake.calls)
