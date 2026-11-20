"""CODER-07B.3 §2 — output-reader failure must not read as success.

The question: when the stdout/stderr drain thread dies, the adapter records the
error in `reader_errors` and `detail` — but does that force `ok=False`?

It is proven here with a controlled process whose read end is closed before the
drain starts, so `os.read` raises EBADF exactly as a real broken pipe would. No
container is created; the Docker CLI is scripted. This is a simulation of the
adapter's decision procedure, not a real-engine measurement.
"""

import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPPORT = os.path.join(ROOT, "tests", "support")
for _path in (ROOT, SUPPORT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import bounded_docker_orchestrator_v1 as orch  # noqa: E402

CID = "c" * 64


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def _proc(rc, stdout=b"", stderr=b""):
    return types.SimpleNamespace(returncode=rc, stdout=stdout, stderr=stderr)


class _Proc(object):
    """Attach client whose pipes can be deliberately broken."""

    def __init__(self, exit_code=0, out=b"ok\n", err=b"", break_stdout=False,
                 break_stderr=False):
        self._out_r, out_w = os.pipe()
        self._err_r, err_w = os.pipe()
        if out:
            os.write(out_w, out)
        if err:
            os.write(err_w, err)
        os.close(out_w)
        os.close(err_w)

        self._broken = []
        if break_stdout:
            os.close(self._out_r)
            self._out_r = -1
            self._broken.append("stdout")
        if break_stderr:
            os.close(self._err_r)
            self._err_r = -1
            self._broken.append("stderr")

        self.stdout = types.SimpleNamespace(fileno=lambda: self._out_r)
        self.stderr = types.SimpleNamespace(fileno=lambda: self._err_r)
        self._exit = exit_code

    def poll(self):
        return self._exit

    def wait(self, timeout=None):
        return self._exit

    def kill(self):
        self._exit = -9


class _Scripted(orch.BoundedDockerOrchestrator):
    def __init__(self, script=None, proc=None):
        super().__init__()
        self.script = dict(script or {})
        self._proc = proc or _Proc()
        self.calls = []

    def _run_docker(self, args, timeout=10800):
        args = list(args)
        self.calls.append(args)
        entry = self.script.get(args[0], _proc(0))
        if isinstance(entry, BaseException):
            raise entry
        return entry

    def _popen(self, args):
        self.calls.append(["popen"] + list(args))
        return self._proc

    def called(self, subcommand):
        return [c for c in self.calls if c[0] == subcommand]


ABSENT = _proc(1, stderr=b"Error: No such object: " + CID.encode())
PRESENT = _proc(0, stdout=CID.encode())
CREATE_OK = _proc(0, stdout=CID.encode())


def _run(proc, inspect=ABSENT):
    orchestrator = _Scripted({"create": CREATE_OK, "inspect": inspect}, proc=proc)
    result = orchestrator.run(
        orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=20))
    return orchestrator, result


# ==========================================================
# BASELINE — a healthy run is still ok
# ==========================================================

def test_a_healthy_run_is_still_ok():
    orchestrator, result = _run(_Proc(0, out=b"c07b1-ok\n"))

    check(result.exit_code == 0, "exit=%r" % (result.exit_code,))
    check(result.ok is True, "a healthy run must be ok, got %r" % (result.ok,))
    check(result.reader_errors == [], "no reader errors expected")
    check(result.removal_verified is True, "cleanup must be verified")


# ==========================================================
# §2a — A FAILED STDOUT READER MUST NOT BE A SUCCESS
# ==========================================================

def test_stdout_reader_failure_is_not_a_successful_execution():
    """RED: the exit code was clean, so the run reported ok despite lost output."""
    orchestrator, result = _run(_Proc(0, out=b"", break_stdout=True))

    check(result.reader_errors, "the failure must be recorded, got %r"
          % (result.reader_errors,))
    check(result.ok is False,
          "a run whose stdout could not be read is not a verified success; "
          "ok=%r" % (result.ok,))


def test_stderr_reader_failure_is_not_a_successful_execution():
    """RED: the same must hold for stderr."""
    orchestrator, result = _run(_Proc(0, out=b"ok\n", break_stderr=True))

    check(result.reader_errors, "the failure must be recorded")
    check(result.ok is False,
          "a run whose stderr could not be read is not a verified success; "
          "ok=%r" % (result.ok,))


def test_a_clean_exit_cannot_override_an_unverified_capture():
    """RED: exit 0 must not outvote a broken output path."""
    orchestrator, result = _run(_Proc(0, out=b"partial", break_stdout=True))

    check(result.exit_code == 0, "the process itself did exit cleanly")
    check(result.ok is False,
          "a clean exit cannot make an unverified capture a success")
    check(result.reason == orch.R_OUTPUT_UNVERIFIED,
          "expected %r, got %r" % (orch.R_OUTPUT_UNVERIFIED, result.reason))


def test_the_reader_failure_reason_is_distinct_from_a_cleanup_failure():
    orchestrator, result = _run(_Proc(0, out=b"", break_stdout=True))

    check(result.reason != orch.R_COMPLETED,
          "a run with a broken reader must not be reported as completed")
    check(result.removal_verified is True,
          "cleanup was fine and must still say so")


# ==========================================================
# §2b — CLEANUP STILL RUNS; REMOVAL STATE STAYS DISTINGUISHABLE
# ==========================================================

def test_cleanup_still_runs_when_the_reader_fails():
    orchestrator, result = _run(_Proc(0, out=b"", break_stdout=True))

    check(orchestrator.called("rm") != [], "cleanup must still be attempted")
    check(orchestrator.called("inspect") != [], "absence must still be verified")
    check(orchestrator.unresolved_container_ids() == [],
          "a verified removal must clear the ledger even after a reader failure")


def test_removal_state_remains_distinguishable_after_a_reader_failure():
    """The capture verdict and the removal verdict are independent facts."""
    orchestrator, result = _run(_Proc(0, out=b"", break_stdout=True), inspect=ABSENT)

    check(result.removal_state == orch.REMOVAL_CONFIRMED,
          "removal must still be reported as confirmed, got %r"
          % (result.removal_state,))
    check(result.removal_verified is True, "removal_verified must still be True")
    check(result.ok is False, "but the run itself is not a verified success")


def test_a_reader_failure_and_a_cleanup_failure_are_both_reported():
    orchestrator, result = _run(
        _Proc(0, out=b"", break_stdout=True),
        inspect=_proc(1, stderr=b"Cannot connect to the Docker daemon"))

    check(result.removal_state == orch.REMOVAL_UNVERIFIED,
          "cleanup must be unverified, got %r" % (result.removal_state,))
    check(result.reader_errors, "the reader failure must not be lost")
    check(result.ok is False, "two independent failures are still not a success")
    check(result.reason == orch.R_CLEANUP_UNVERIFIED,
          "the cleanup verdict takes precedence in the reason, got %r"
          % (result.reason,))


# ==========================================================
# §2c — THE EVIDENCE MUST NOT BE DISCARDED
# ==========================================================

def test_reader_evidence_is_retained_in_the_result():
    orchestrator, result = _run(_Proc(0, out=b"", break_stdout=True))

    check(isinstance(result.reader_errors, list) and result.reader_errors,
          "reader_errors must carry the failure, got %r" % (result.reader_errors,))
    check(any("stdout" in e for e in result.reader_errors),
          "the failing stream must be named, got %r" % (result.reader_errors,))
    check("reader" in (result.detail or "").lower(),
          "detail must mention the reader failure, got %r" % (result.detail,))


def test_the_capture_object_records_the_error_itself():
    capture = orch._Capture(1024)
    read_fd, write_fd = os.pipe()
    os.close(write_fd)
    os.close(read_fd)

    orch._drain(read_fd, "stderr", capture)

    check(capture.errors, "the capture must record the failure")
    check("stderr reader" in capture.errors[0], "errors=%r" % (capture.errors,))


# ==========================================================
# §2d — THE BOUNDARY DESCRIPTION MUST DECLARE THE RULE
# ==========================================================

def test_boundary_declares_that_reader_failure_fails_the_run():
    described = orch.describe_boundary()
    check(described.get("reader_failure_fails_the_run") is True,
          "the boundary must state that an unreadable stream fails the run")
    check(orch.R_OUTPUT_UNVERIFIED in described["cleanup_outcomes"]
          or orch.R_OUTPUT_UNVERIFIED in described.get("outcome_reasons", []),
          "the reader-failure outcome must be discoverable")
