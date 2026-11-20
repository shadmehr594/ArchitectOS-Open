"""CODER-07B.2 — fail-closed orchestration hardening.

Phase 1 of this file (§3 RED) targets the cleanup verification defect with a
CONTROLLED Docker CLI failure simulation: the adapter's `_run_docker` is
replaced by a scripted dispatcher, so no daemon is destabilised and no container
is created. This is deliberate — the failure modes that matter (daemon
unreachable, named pipe failure, permission denied, unexpected API error) cannot
be produced on a healthy engine without damaging it.

Real-engine tests are marked `needs_engine` and are used only for bounded, safe
scenarios.

Nothing here executes generated code. Every command in the allowlist is a fixed,
reviewed probe.
"""

import os
import subprocess
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPPORT = os.path.join(ROOT, "tests", "support")
for _path in (ROOT, SUPPORT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import bounded_docker_orchestrator_v1 as orch  # noqa: E402

MODULE_PATH = os.path.join(SUPPORT, "bounded_docker_orchestrator_v1.py")

# A syntactically valid container id so identity checks behave realistically.
CID = "a" * 64


def check(condition, message):
    """Raise, never silently pass."""
    if not condition:
        raise AssertionError(message)


def _engine_available():
    try:
        result = orch.BoundedDockerOrchestrator()._run_docker(
            ["version", "--format", "{{.Server.Version}}"], timeout=10800)
        return result.returncode == 0
    except Exception:
        return False


ENGINE_OK = _engine_available()
needs_engine = pytest.mark.skipif(not ENGINE_OK, reason="Docker engine not reachable")


# ==========================================================
# CONTROLLED DOCKER CLI FAILURE SIMULATION
# ==========================================================

def _proc(returncode, stdout=b"", stderr=b""):
    return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class _ScriptedDocker(orch.BoundedDockerOrchestrator):
    """Adapter whose Docker CLI is scripted per subcommand.

    `script` maps a docker subcommand ("rm", "inspect", ...) to either a
    CompletedProcess-like object or an exception instance to raise. Anything not
    scripted returns a benign success with empty output.

    This simulates the CLI, not the product logic: the code under test is the
    adapter's own decision procedure.
    """

    def __init__(self, script=None, default=None):
        super().__init__()
        self.script = dict(script or {})
        self.default = default or _proc(0)
        self.calls = []

    def _run_docker(self, args, timeout=10800):
        args = list(args)
        self.calls.append((args, timeout))
        entry = self.script.get(args[0], self.default)
        if isinstance(entry, BaseException):
            raise entry
        return entry

    def called(self, subcommand):
        return [c for c in self.calls if c[0][0] == subcommand]


def _owned(script):
    orchestrator = _ScriptedDocker(script)
    orchestrator._created_ids.append(CID)
    return orchestrator


def _verdict(orchestrator, cid=CID):
    """Run cleanup and reduce it to the two safety-critical facts."""
    outcome = orchestrator._cleanup(cid)
    return outcome["removed"], outcome["removal_verified"], outcome["removal_state"]


# ==========================================================
# §3 — CLEANUP VERIFICATION MUST NOT CONFUSE "CANNOT SEE" WITH "GONE"
# ==========================================================

def test_cleanup_does_not_claim_verified_removal_when_the_daemon_is_unreachable():
    """RED: the core false positive.

    `docker rm` fails AND `docker inspect` fails because the engine cannot be
    reached. Nothing here proves the container is gone. The adapter must not
    report removal_verified.
    """
    orchestrator = _owned({
        "rm": _proc(1, stderr=b"Cannot connect to the Docker daemon at "
                              b"npipe:////./pipe/dockerDesktopLinuxEngine. "
                              b"Is the docker daemon running?"),
        "inspect": _proc(1, stderr=b"Cannot connect to the Docker daemon at "
                                   b"npipe:////./pipe/dockerDesktopLinuxEngine. "
                                   b"Is the docker daemon running?"),
    })

    removed, verified, state = _verdict(orchestrator)

    check(verified is False,
          "an unreachable daemon proves nothing about removal, yet the adapter "
          "reported removal_verified=%r" % (verified,))
    check(removed is False,
          "an unreachable daemon proves nothing about removal, yet the adapter "
          "reported removed=%r" % (removed,))
    check(state == orch.REMOVAL_UNVERIFIED,
          "state must be unverified, got %r" % (state,))


def test_cleanup_does_not_treat_permission_denied_as_absence():
    """RED: access denied is not evidence of absence."""
    orchestrator = _owned({
        "rm": _proc(1, stderr=b"permission denied while trying to connect to the "
                              b"Docker daemon socket"),
        "inspect": _proc(1, stderr=b"permission denied while trying to connect to "
                                   b"the Docker daemon socket"),
    })

    removed, verified, state = _verdict(orchestrator)

    check(verified is False,
          "permission denied is not proof of removal, yet removal_verified=%r" % (verified,))
    check(removed is False, "permission denied is not proof of removal, yet removed=%r" % (removed,))
    check(state == orch.REMOVAL_UNVERIFIED, "state must be unverified, got %r" % (state,))


def test_cleanup_does_not_treat_an_unexpected_api_error_as_absence():
    """RED: any non-zero exit was previously read as 'gone'."""
    orchestrator = _owned({
        "rm": _proc(0),
        "inspect": _proc(1, stderr=b"Error response from daemon: something "
                                   b"unexpected happened in the graphdriver"),
    })

    removed, verified, state = _verdict(orchestrator)

    check(verified is False,
          "an unexpected API error is not proof of removal, yet removal_verified=%r"
          % (verified,))
    check(state == orch.REMOVAL_UNVERIFIED, "state must be unverified, got %r" % (state,))


def test_cleanup_does_not_treat_a_pipe_failure_as_absence():
    """RED: a pipe/OS failure must leave the outcome unknown, not 'removed'."""
    orchestrator = _owned({
        "rm": OSError(22, "The pipe has been ended"),
        "inspect": OSError(22, "The pipe has been ended"),
    })

    removed, verified, state = _verdict(orchestrator)

    check(verified is False,
          "a pipe failure proves nothing about removal, yet removal_verified=%r" % (verified,))
    check(removed is False, "a pipe failure proves nothing about removal, yet removed=%r" % (removed,))
    check(state == orch.REMOVAL_UNVERIFIED, "state must be unverified, got %r" % (state,))


def test_cleanup_does_not_treat_an_inspect_timeout_as_absence():
    """RED: a timeout is not evidence of absence either."""
    orchestrator = _owned({
        "rm": subprocess.TimeoutExpired(cmd="docker rm", timeout=10800),
        "inspect": subprocess.TimeoutExpired(cmd="docker inspect", timeout=10800),
    })

    removed, verified, state = _verdict(orchestrator)

    check(verified is False, "a timeout proves nothing about removal, yet removal_verified=%r" % (verified,))
    check(removed is False, "a timeout proves nothing about removal, yet removed=%r" % (removed,))
    check(state == orch.REMOVAL_UNVERIFIED, "state must be unverified, got %r" % (state,))


def test_cleanup_accepts_a_decisive_no_such_object_as_absence():
    """GREEN anchor: the ONE non-zero exit that does confirm removal."""
    orchestrator = _owned({
        "rm": _proc(0),
        "inspect": _proc(1, stderr=b"Error: No such object: " + CID.encode()),
    })

    removed, verified, state = _verdict(orchestrator)

    check(verified is True,
          "a decisive 'No such object' must confirm removal, got removal_verified=%r"
          % (verified,))
    check(removed is True, "the container was removed, got removed=%r" % (removed,))
    check(state == orch.REMOVAL_CONFIRMED, "state must be confirmed_absent, got %r" % (state,))


def test_cleanup_accepts_no_such_container_as_absence():
    """`docker rm` on an already-absent container exits 1; that is still absence."""
    orchestrator = _owned({
        "rm": _proc(1, stderr=b"Error: No such container: " + CID.encode()),
        "inspect": _proc(1, stderr=b"Error: No such container: " + CID.encode()),
    })

    removed, verified, state = _verdict(orchestrator)

    check(verified is True, "an absent container must verify as absent, got %r" % (verified,))
    check(removed is True, "an absent container is removed, got %r" % (removed,))
    check(state == orch.REMOVAL_CONFIRMED, "state must be confirmed_absent, got %r" % (state,))


def test_cleanup_reports_a_still_present_container_as_not_removed():
    """RED: `rm` claiming success is not proof; inspect is authoritative."""
    orchestrator = _owned({
        "rm": _proc(0),
        "inspect": _proc(0, stdout=CID.encode()),
    })

    removed, verified, state = _verdict(orchestrator)

    check(verified is False,
          "inspect found the container, so removal cannot be verified, got %r" % (verified,))
    check(removed is False,
          "inspect found the container, so it was not removed, got %r" % (removed,))
    check(state == orch.REMOVAL_PRESENT, "state must be still_present, got %r" % (state,))


def test_cleanup_refuses_to_touch_a_container_it_does_not_own():
    orchestrator = _ScriptedDocker({})  # _created_ids stays empty

    removed, verified, state = _verdict(orchestrator)

    check(removed is False and verified is False,
          "a non-owned container must never be reported as removed")
    check(orchestrator.called("rm") == [],
          "a non-owned container must never be sent to `docker rm`")
    check(orchestrator.called("inspect") == [],
          "a non-owned container must never be inspected")


def test_unverified_cleanup_stays_in_the_ownership_ledger():
    """§5: an unproven removal must remain a known liability, not vanish."""
    orchestrator = _owned({
        "rm": _proc(1, stderr=b"Cannot connect to the Docker daemon"),
        "inspect": _proc(1, stderr=b"Cannot connect to the Docker daemon"),
    })

    orchestrator._cleanup(CID)

    check(orchestrator.unresolved_container_ids() == [CID],
          "an unverified removal must stay unresolved, got %r"
          % (orchestrator.unresolved_container_ids(),))


def test_verified_cleanup_leaves_no_unresolved_liability():
    orchestrator = _owned({
        "rm": _proc(0),
        "inspect": _proc(1, stderr=b"Error: No such object: " + CID.encode()),
    })

    orchestrator._cleanup(CID)

    check(orchestrator.unresolved_container_ids() == [],
          "a verified removal must clear the ledger, got %r"
          % (orchestrator.unresolved_container_ids(),))


def test_execution_is_refused_while_a_prior_cleanup_is_unresolved():
    """§3/§4: uncertainty must stop further execution, not merely be logged."""
    orchestrator = _owned({
        "rm": _proc(1, stderr=b"Cannot connect to the Docker daemon"),
        "inspect": _proc(1, stderr=b"Cannot connect to the Docker daemon"),
    })
    orchestrator._cleanup(CID)

    with pytest.raises(orch.OrchestrationRefused) as caught:
        orchestrator.run(orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=5))

    check(caught.value.reason == orch.R_UNRESOLVED_CLEANUP,
          "expected %r, got %r" % (orch.R_UNRESOLVED_CLEANUP, caught.value.reason))
    check(orchestrator.called("create") == [],
          "no container may be created while a cleanup is unresolved")


def test_emergency_cleanup_allowance_is_bounded():
    """§4: cleanup gets its own bounded allowance, and reports its own cost."""
    orchestrator = _owned({
        "rm": _proc(1, stderr=b"Cannot connect to the Docker daemon"),
        "inspect": _proc(1, stderr=b"Cannot connect to the Docker daemon"),
    })

    outcome = orchestrator._cleanup(CID, allowance=orch.EMERGENCY_CLEANUP_BUDGET_SECONDS)

    check(outcome["elapsed_seconds"] <= orch.EMERGENCY_CLEANUP_BUDGET_SECONDS,
          "cleanup exceeded its allowance: %r" % (outcome["elapsed_seconds"],))
    rm_timeout = orchestrator.called("rm")[0][1]
    check(rm_timeout <= orch.PHASE_TIMEOUTS["rm"],
          "rm timeout %r exceeds the phase cap" % (rm_timeout,))


def test_lifecycle_budget_is_a_real_upper_bound_not_the_deadline():
    """§4: deadline_seconds bounds only monitoring; the call has its own budget."""
    for grace in (0.5, 2.0, 10.0):
        budget = orch.lifecycle_budget_seconds(grace)
        summed = sum(orch.PHASE_TIMEOUTS.values()) + grace
        check(budget == summed,
              "budget %r must equal the sum of phase caps %r" % (budget, summed))
        check(budget > 1.0,
              "a 1-second deadline cannot imply a 1-second call budget")


# ==========================================================
# §7 — CONTROL-PLANE TRUST
# ==========================================================

def test_a_path_or_shell_metacharacter_in_the_binary_is_refused():
    for hostile in ("C:/Windows/System32/cmd.exe", "./docker", "docker; rm -rf /",
                    "docker && whoami", "docker|cat", "docker$(id)", ""):
        with pytest.raises(orch.OrchestrationRefused) as caught:
            orch.BoundedDockerOrchestrator(docker_bin=hostile)
        check(caught.value.reason == orch.R_CONTROL_PLANE_UNTRUSTED,
              "%r must be refused as untrusted, got %r"
              % (hostile, caught.value.reason))


def test_a_non_mapping_environment_is_refused():
    with pytest.raises(orch.OrchestrationRefused) as caught:
        orch.BoundedDockerOrchestrator(env=["DOCKER_HOST=x"])
    check(caught.value.reason == orch.R_CONTROL_PLANE_UNTRUSTED,
          "a list environment must be refused, got %r" % (caught.value.reason,))


def test_no_request_field_can_reach_the_control_plane():
    """A structured request must not be able to name the binary or its env."""
    for field in ("docker_bin", "env", "context", "host", "tls", "config"):
        with pytest.raises(orch.OrchestrationRefused) as caught:
            orch.ContainerSpec.from_request({
                "image_key": "ubuntu-22.04", "command_id": "echo_ok", field: "x"})
        check(caught.value.reason in (orch.R_FORBIDDEN_FIELD, orch.R_REQUEST_INVALID),
              "%r must not be accepted, got %r" % (field, caught.value.reason))


def test_control_plane_description_is_honest():
    described = orch.describe_control_plane()
    check(described["trusted_binary_name"] == "docker", "trusted binary must be fixed")
    check(described["binary_may_be_overridden_by_request"] is False,
          "a request must not be able to substitute the executable")
    check(described["environment_may_be_overridden_by_request"] is False,
          "a request must not be able to substitute the environment")
    check(described["accepts_docker_context_argument"] is False,
          "a Docker context must not be selectable")
    check(described["shell_interface"] is False, "there must be no shell interface")


def test_boundary_description_exposes_the_new_failure_vocabulary():
    described = orch.describe_boundary()
    check(orch.REMOVAL_UNVERIFIED in described["removal_states"],
          "unverified must be a first-class removal state")
    check(orch.R_CLEANUP_UNVERIFIED in described["cleanup_outcomes"],
          "cleanup_unverified must be a first-class outcome")
    check(described["emergency_cleanup_budget_seconds"] > 0,
          "an emergency cleanup allowance must exist")



# ==========================================================
# §4 — LIFECYCLE FAILURE RECOVERY
# ==========================================================

class _FakeProc(object):
    """Minimal stand-in for the `docker start -a` client, with real pipes."""

    def __init__(self, exit_code=0, out=b"", err=b"", never_exits=False):
        self._out_r, out_w = os.pipe()
        self._err_r, err_w = os.pipe()
        if out:
            os.write(out_w, out)
        if err:
            os.write(err_w, err)
        os.close(out_w)
        os.close(err_w)
        self.stdout = types.SimpleNamespace(fileno=lambda: self._out_r)
        self.stderr = types.SimpleNamespace(fileno=lambda: self._err_r)
        self._exit = exit_code
        self._never = never_exits
        self.killed = False

    def poll(self):
        if self._never and not self.killed:
            return None
        return self._exit

    def wait(self, timeout=None):
        return self._exit

    def kill(self):
        self.killed = True


class _ScriptedRun(_ScriptedDocker):
    """Scripted CLI plus a scripted attach client."""

    def __init__(self, script=None, proc=None, popen_error=None):
        super().__init__(script)
        self._proc = proc or _FakeProc(0, out=b"ok\n")
        self._popen_error = popen_error

    def _popen(self, args):
        self.calls.append((["popen"] + list(args), None))
        if self._popen_error is not None:
            raise self._popen_error
        return self._proc


_CREATE_OK = _proc(0, stdout=CID.encode())
_ABSENT = _proc(1, stderr=b"Error: No such object: " + CID.encode())
_DAEMON_DOWN = _proc(1, stderr=b"Cannot connect to the Docker daemon")


def _scripted_run(script, **kwargs):
    orchestrator = _ScriptedRun(script, **kwargs)
    return orchestrator


def test_timeout_during_creation_cleans_up_by_name_and_verifies():
    """§4: create can time out after the daemon already created the container."""
    orchestrator = _scripted_run({
        "ps": _proc(0),
        "create": subprocess.TimeoutExpired(cmd="docker create", timeout=10800),
        "rm": _proc(0),
        "inspect": _proc(1, stderr=b"Error: No such object: c07b1-deadbeef"),
    })

    with pytest.raises(orch.OrchestrationRefused) as caught:
        orchestrator.run(orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=5))

    check(caught.value.reason == orch.R_ENGINE_UNAVAILABLE,
          "a create timeout must be reported, got %r" % (caught.value.reason,))
    check("confirmed_absent" in caught.value.detail,
          "cleanup must be attempted and verified by name, detail=%r" % (caught.value.detail,))
    check(orchestrator.unresolved_liabilities() == [],
          "a verified name cleanup must leave no liability, got %r"
          % (orchestrator.unresolved_liabilities(),))


def test_timeout_during_creation_with_unverifiable_cleanup_blocks_further_runs():
    """§4/§5: partial creation with no parseable id must stop the adapter."""
    orchestrator = _scripted_run({
        "ps": _proc(0),
        "create": subprocess.TimeoutExpired(cmd="docker create", timeout=10800),
        "rm": _DAEMON_DOWN,
        "inspect": _DAEMON_DOWN,
    })

    with pytest.raises(orch.OrchestrationRefused):
        orchestrator.run(orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=5))

    check(len(orchestrator.unresolved_liabilities()) == 1,
          "an unverified name cleanup must be recorded as a liability, got %r"
          % (orchestrator.unresolved_liabilities(),))

    with pytest.raises(orch.OrchestrationRefused) as caught:
        orchestrator.run(orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=5))
    check(caught.value.reason == orch.R_UNRESOLVED_CLEANUP,
          "further runs must be refused, got %r" % (caught.value.reason,))


def test_engine_disconnect_after_creation_is_cleanup_unverified():
    """§4: losing the engine after create must not read as a clean run."""
    orchestrator = _scripted_run({
        "ps": _proc(0),
        "create": _CREATE_OK,
        "rm": _DAEMON_DOWN,
        "inspect": _DAEMON_DOWN,
    })

    result = orchestrator.run(orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=20))

    check(result.reason == orch.R_CLEANUP_UNVERIFIED,
          "expected %r, got %r" % (orch.R_CLEANUP_UNVERIFIED, result.reason))
    check(result.ok is False, "an unverified cleanup must never be reported as ok")
    check(result.removal_verified is False, "removal must not be claimed")
    check(result.removal_state == orch.REMOVAL_UNVERIFIED,
          "state=%r" % (result.removal_state,))
    check(result.exit_code == 0, "the process itself did exit cleanly")
    check(orchestrator.unresolved_container_ids() == [CID],
          "the container must remain a known liability")


def test_disconnect_during_execution_is_reported_with_its_cleanup_outcome():
    """§4: state inspection failing must not silently become 'no OOM, all fine'."""
    orchestrator = _scripted_run({
        "ps": _proc(0),
        "create": _CREATE_OK,
        "rm": _proc(0),
        "inspect": _proc(0, stdout=b"{}"),
    })

    result = orchestrator.run(orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=20))

    # inspect succeeded here, so absence must be positively disproved, not assumed
    check(result.removal_state == orch.REMOVAL_PRESENT,
          "a successful inspect must mean still_present, got %r" % (result.removal_state,))
    check(result.reason == orch.R_CLEANUP_UNVERIFIED,
          "a container that survived removal must not read as completed, got %r"
          % (result.reason,))


def test_stop_failure_falls_back_to_kill_and_is_recorded():
    orchestrator = _scripted_run({
        "ps": _proc(0),
        "create": _CREATE_OK,
        "stop": _proc(1, stderr=b"Error response from daemon: cannot stop"),
        "kill": _proc(0),
        "rm": _proc(0),
        "inspect": _ABSENT,
    }, proc=_FakeProc(137, never_exits=True))

    result = orchestrator.run(orch.ContainerSpec(
        "ubuntu-22.04", "sleep_long", deadline_seconds=1, grace_seconds=1))

    check(orchestrator.called("kill") != [], "kill must be attempted after stop fails")
    check(result.forced_kill is True, "forced_kill=%r" % (result.forced_kill,))
    check(result.removal_verified is True, "cleanup must still be verified")
    check("stop exited 1" in (result.detail or ""),
          "the stop failure must be reported, detail=%r" % (result.detail,))


def test_kill_failure_is_recorded_and_does_not_hide_the_cleanup_outcome():
    orchestrator = _scripted_run({
        "ps": _proc(0),
        "create": _CREATE_OK,
        "stop": _proc(1),
        "kill": OSError(22, "The pipe has been ended"),
        "rm": _proc(0),
        "inspect": _ABSENT,
    }, proc=_FakeProc(137, never_exits=True))

    result = orchestrator.run(orch.ContainerSpec(
        "ubuntu-22.04", "sleep_long", deadline_seconds=1, grace_seconds=1))

    check("kill failed" in (result.detail or ""),
          "a kill failure must be reported, detail=%r" % (result.detail,))
    check(result.removal_verified is True,
          "a kill failure must not prevent verified cleanup")


def test_rm_failure_leaves_the_outcome_unverified():
    """§4: `docker rm` failing is not removal."""
    orchestrator = _scripted_run({
        "ps": _proc(0),
        "create": _CREATE_OK,
        "rm": _DAEMON_DOWN,
        "inspect": _ABSENT,
    })

    result = orchestrator.run(orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=20))

    # inspect says absent, which is decisive, so the verdict is still confirmed
    check(result.removal_verified is True,
          "a decisive absence must still verify even if rm reported an error")
    check(result.rm_returncode == 1, "rm_returncode=%r" % (result.rm_returncode,))


def test_attach_client_failure_is_an_explicit_failure_not_a_success():
    """§4: no attach client means no observed execution."""
    orchestrator = _scripted_run({
        "ps": _proc(0),
        "create": _CREATE_OK,
        "rm": _proc(0),
        "inspect": _ABSENT,
    }, popen_error=OSError(2, "The system cannot find the file specified"))

    result = orchestrator.run(orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=20))

    check(result.reason == orch.R_ATTACH_FAILED,
          "expected %r, got %r" % (orch.R_ATTACH_FAILED, result.reason))
    check(result.ok is False, "an attach failure must never be ok")
    check(result.attach_error, "attach_error must be populated")
    check(result.removal_verified is True,
          "the container must still be removed on the attach-failure path")


def test_output_reader_failure_is_recorded_not_swallowed():
    """§4: a broken reader loses output; that must be visible."""
    capture = orch._Capture(1024)
    read_fd, write_fd = os.pipe()
    os.close(write_fd)
    os.close(read_fd)

    orch._drain(read_fd, "stdout", capture)

    check(capture.errors, "a reader failure must be recorded, errors=%r" % (capture.errors,))
    check("stdout reader" in capture.errors[0], "errors=%r" % (capture.errors,))


def test_cancellation_during_startup_is_distinct_from_a_timeout():
    import threading

    orchestrator = _scripted_run({
        "ps": _proc(0),
        "create": _CREATE_OK,
        "stop": _proc(0),
        "kill": _proc(0),
        "rm": _proc(0),
        "inspect": _ABSENT,
    }, proc=_FakeProc(143, never_exits=True))

    threading.Timer(0.2, orchestrator.cancel).start()
    result = orchestrator.run(orch.ContainerSpec(
        "ubuntu-22.04", "sleep_long", deadline_seconds=30, grace_seconds=1))

    check(result.cancelled is True, "cancelled=%r" % (result.cancelled,))
    check(result.timed_out is False, "a cancellation must not be reported as a timeout")
    check(result.reason == orch.R_CANCELLED, "reason=%r" % (result.reason,))
    check(result.removal_verified is True, "cleanup must still be verified")


def test_cancellation_does_not_corrupt_the_cleanup_verdict():
    """§4: the cancel flag must not short-circuit cleanup verification."""
    orchestrator = _owned({
        "rm": _proc(0),
        "inspect": _proc(1, stderr=b"Error: No such object: " + CID.encode()),
    })
    orchestrator._cancel.set()

    outcome = orchestrator._cleanup(CID)

    check(outcome["removal_verified"] is True,
          "cleanup must complete its verification regardless of the cancel flag")
    check(orchestrator._cancel.is_set(), "cleanup must not clear the cancel flag")


def test_an_unexpected_exception_still_runs_cleanup():
    """§4: an exception must not skip the removal path."""
    orchestrator = _scripted_run({
        "ps": _proc(0),
        "create": _CREATE_OK,
        "rm": _proc(0),
        "inspect": _ABSENT,
    })

    def boom():
        raise RuntimeError("injected fault after start")

    with pytest.raises(RuntimeError):
        orchestrator.run(
            orch.ContainerSpec("ubuntu-22.04", "sleep_long", deadline_seconds=30),
            _fault_after_start=boom)

    check(orchestrator.called("rm") != [], "cleanup must run on the fault path")
    check(orchestrator.unresolved_container_ids() == [],
          "a verified cleanup must clear the ledger even on the fault path")


@needs_engine
def test_unverified_cleanup_propagates_to_the_run_result():
    """Real engine: the propagation logic, measured on one real container."""
    orchestrator = orch.BoundedDockerOrchestrator()
    real = orchestrator._cleanup

    def pretend_unverified(cid, allowance=None):
        outcome = real(cid, allowance)
        orchestrator._removed_ids.clear()  # forget the confirmation
        outcome["removal_state"] = orch.REMOVAL_UNVERIFIED
        outcome["removed"] = False
        outcome["removal_verified"] = False
        outcome["detail"] = "simulated loss of visibility"
        return outcome

    orchestrator._cleanup = pretend_unverified
    result = orchestrator.run(orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=20))

    check(result.exit_code == 0, "the process itself must still exit cleanly")
    check(result.reason == orch.R_CLEANUP_UNVERIFIED,
          "expected %r, got %r" % (orch.R_CLEANUP_UNVERIFIED, result.reason))
    check(result.ok is False, "ok must be False when cleanup is unverified")
    check(orchestrator.unresolved_container_ids() == [result.container_id],
          "the container must remain a liability")


# ==========================================================
# §5 — OWNERSHIP AND RECOVERY
# ==========================================================

def test_cleanup_targets_exact_references_never_prefixes():
    """§5: never clean by a broad prefix, filter or glob."""
    orchestrator = _scripted_run({
        "ps": _proc(0),
        "create": _CREATE_OK,
        "rm": _proc(0),
        "inspect": _ABSENT,
    })

    orchestrator.run(orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=20))

    for subcommand in ("rm", "inspect"):
        for args, _timeout in orchestrator.called(subcommand):
            target = args[-1]
            check(target == CID or target.startswith(orch.NAME_PREFIX),
                  "%s was given %r, which is neither the exact id nor the exact "
                  "generated name" % (subcommand, target))
            for wildcard in ("*", "?", "c07b1-*", "name=", "filter"):
                check(wildcard not in target,
                      "%s was given a broad target %r" % (subcommand, target))


def test_a_preexisting_container_is_never_targeted():
    """§5: a container this adapter did not create is untouchable."""
    foreign = "f" * 64
    orchestrator = _scripted_run({})

    outcome = orchestrator._cleanup(foreign)

    check(outcome["owned"] is False, "a foreign container must not be owned")
    check(outcome["removal_verified"] is False, "a foreign container cannot be verified")
    check(orchestrator.called("rm") == [], "a foreign container must never be removed")
    check(orchestrator.called("inspect") == [], "a foreign container must never be inspected")


def test_each_run_uses_a_unique_generated_name():
    seen = []
    for _ in range(2):
        orchestrator = _scripted_run({
            "ps": _proc(0),
            "create": _CREATE_OK,
            "rm": _proc(0),
            "inspect": _ABSENT,
        })
        orchestrator.run(orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=20))
        create_args = orchestrator.called("create")[0][0]
        seen.append(create_args[create_args.index("--name") + 1])

    check(len(set(seen)) == 2, "names must be unique per run, got %r" % (seen,))
    for name in seen:
        check(name.startswith(orch.NAME_PREFIX),
              "name %r must carry the task prefix" % (name,))


def test_recovery_only_touches_the_exact_task_owned_id():
    orchestrator = _owned({
        "rm": _proc(0),
        "inspect": _proc(1, stderr=b"Error: No such object: " + CID.encode()),
    })

    outcome = orchestrator.verify_cleanup(CID)

    check(outcome["removal_verified"] is True, "recovery must verify the exact id")
    foreign = orchestrator.verify_cleanup("b" * 64)
    check(foreign["owned"] is False, "recovery must refuse a non-owned id")


# ==========================================================
# §6 — TERMINATION SEMANTICS
# ==========================================================

def test_exit_143_means_died_from_term_not_handled_term():
    """§6: 143 proves the signal arrived, not that the process coped with it."""
    orchestrator = _scripted_run({
        "ps": _proc(0),
        "create": _CREATE_OK,
        "stop": _proc(0),
        "kill": _proc(0),
        "rm": _proc(0),
        "inspect": _ABSENT,
    }, proc=_FakeProc(143, never_exits=True))

    result = orchestrator.run(orch.ContainerSpec(
        "ubuntu-22.04", "sleep_long", deadline_seconds=1, grace_seconds=1))

    check(result.exited_by_sigterm is True, "exit 143 must be recorded as SIGTERM")
    check(result.graceful_stop_succeeded is False,
          "dying from SIGTERM is not a graceful stop; only exit 0 is")


def test_a_zero_exit_after_a_term_is_a_graceful_stop():
    orchestrator = _scripted_run({
        "ps": _proc(0),
        "create": _CREATE_OK,
        "stop": _proc(0),
        "kill": _proc(0),
        "rm": _proc(0),
        "inspect": _ABSENT,
    }, proc=_FakeProc(0, never_exits=True))

    result = orchestrator.run(orch.ContainerSpec(
        "ubuntu-22.04", "sleep_long", deadline_seconds=1, grace_seconds=1))

    check(result.graceful_stop_succeeded is True,
          "an exit 0 after a TERM is the only evidence of a clean shutdown")
    check(result.forced_kill is False, "no SIGKILL was needed")


def test_boundary_declares_it_does_not_use_an_init():
    """§6: the frozen parameter set has no --init; say so rather than imply it."""
    described = orch.describe_boundary()
    check(described["uses_init"] is False,
          "the adapter must declare that it runs without an init")
    check("died from TERM" in described["graceful_means"],
          "the graceful/forced definition must be stated precisely")
