"""CODER-07B.1 — bounded orchestration controls A–L.

These are INTEGRATION tests against the real Docker engine. They create real
containers and must leave none behind. Mocks are not accepted here: the whole
point of this phase is that the earlier controls were verified by measurement.

What is executed: fixed, reviewed probes from the adapter's allowlist. Nothing
is generated, nothing is user-supplied, no ArchitectOS source is mounted, and no
AI-generated program runs at any point.
"""

import ast
import os
import sys
import threading
import tokenize

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUPPORT = os.path.join(ROOT, "tests", "support")
for _path in (ROOT, SUPPORT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import bounded_docker_orchestrator_v1 as orch  # noqa: E402
from core.execution import execution_contract_v1 as ec  # noqa: E402

MODULE_PATH = os.path.join(SUPPORT, "bounded_docker_orchestrator_v1.py")

_NON_CODE_TOKENS = frozenset({
    tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE,
    tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING, tokenize.ENDMARKER,
})


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


def snapshot_containers(orchestrator):
    """Identity snapshot only.

    Deliberately excludes Status: a running container's status string changes
    over time ("Up 15 minutes"), so including it would make this comparison fail
    for a reason that has nothing to do with the adapter.
    """
    result = orchestrator._run_docker(
        ["ps", "-a", "--format", "{{.ID}}|{{.Names}}"], timeout=10800)
    return sorted(result.stdout.decode("utf-8", "replace").splitlines())


def leftover_task_containers(orchestrator):
    result = orchestrator._run_docker(
        ["ps", "-a", "--filter", "name=c07b1-", "--format", "{{.Names}}"], timeout=10800)
    return [n for n in result.stdout.decode("utf-8", "replace").split() if n]


# ==========================================================
# PRECONDITION — a stopped engine must never look like a pass
# ==========================================================

def test_engine_is_available_so_this_suite_cannot_pass_vacuously():
    check(ENGINE_OK,
          "Docker engine unreachable: the A-L controls cannot be verified, so this "
          "suite must fail rather than skip silently")


# ==========================================================
# A. NORMAL COMPLETION
# ==========================================================

@needs_engine
def test_a_normal_completion():
    orchestrator = orch.BoundedDockerOrchestrator()
    result = orchestrator.run(orch.ContainerSpec(
        "ubuntu-22.04", "echo_ok", deadline_seconds=20))

    check(result.exit_code == 0, "exit_code=%r" % (result.exit_code,))
    check("c07b1-ok" in result.stdout, "stdout=%r" % (result.stdout,))
    check(result.reason == orch.R_COMPLETED, "reason=%r" % (result.reason,))
    check(result.ok is True, "ok must be True on a clean exit")
    check(result.truncated is False, "a small output must not be truncated")
    check(result.timed_out is False and result.cancelled is False, "must not time out or cancel")
    check(result.removed is True and result.removal_verified is True,
          "container must be removed and absence verified by id")


# ==========================================================
# B. OUTPUT EXCEEDS THE BYTE LIMIT
# ==========================================================

@needs_engine
def test_b_output_cap_is_enforced_without_unbounded_buffering():
    orchestrator = orch.BoundedDockerOrchestrator()
    cap = 4096
    result = orchestrator.run(orch.ContainerSpec(
        "ubuntu-22.04", "flood_output", max_output_bytes=cap, deadline_seconds=30))

    check(result.truncated is True, "1 MiB of output against a 4096-byte cap must truncate")
    check(result.captured_bytes <= cap,
          "captured=%r exceeded cap=%r" % (result.captured_bytes, cap))
    check(result.discarded_bytes > 0, "discarded=%r" % (result.discarded_bytes,))
    check(len(result.stdout) + len(result.stderr) <= cap,
          "returned payload exceeds the cap: %d" % (len(result.stdout) + len(result.stderr)))
    check(result.exit_code == 0, "exit_code=%r" % (result.exit_code,))
    check(result.removed is True and result.removal_verified is True, "cleanup")


# ==========================================================
# C. PROCESS EXCEEDS ITS WALL-CLOCK DEADLINE
# ==========================================================

@needs_engine
def test_c_wall_clock_deadline_is_enforced_outside_the_container():
    orchestrator = orch.BoundedDockerOrchestrator()
    result = orchestrator.run(orch.ContainerSpec(
        "ubuntu-22.04", "sleep_long", deadline_seconds=2, grace_seconds=1))

    check(result.timed_out is True, "a 600 s sleep under a 2 s deadline must time out")
    check(result.reason == orch.R_DEADLINE_EXCEEDED, "reason=%r" % (result.reason,))
    check(result.ok is False, "a timed-out run is not ok")
    check(result.duration_seconds < 30,
          "deadline not honoured: duration=%r" % (result.duration_seconds,))
    check(result.exit_code in (137, 143),
          "expected a signal exit, got %r" % (result.exit_code,))
    check(result.removed is True and result.removal_verified is True, "cleanup")


# ==========================================================
# D. IGNORES GRACEFUL TERMINATION -> FORCED STOP
# ==========================================================

@needs_engine
def test_d_forced_termination_when_the_process_ignores_sigterm():
    orchestrator = orch.BoundedDockerOrchestrator()
    result = orchestrator.run(orch.ContainerSpec(
        "ubuntu-22.04", "sleep_long", deadline_seconds=2, grace_seconds=1))

    check(result.timed_out is True, "must reach the deadline")
    # `sleep` runs as PID 1 and does not handle SIGTERM, so the stop escalates.
    check(result.exit_code == 137,
          "expected SIGKILL (137), got %r" % (result.exit_code,))
    check(result.forced_kill is True, "forced kill must be reported")
    check(result.graceful_stop_succeeded is False,
          "SIGTERM was ignored; a graceful stop must not be reported")
    check(result.removed is True and result.removal_verified is True, "cleanup")


# ==========================================================
# E. NONZERO EXIT CODE
# ==========================================================

@needs_engine
def test_e_nonzero_exit_is_reported_accurately():
    orchestrator = orch.BoundedDockerOrchestrator()
    result = orchestrator.run(orch.ContainerSpec(
        "ubuntu-22.04", "exit_nonzero", deadline_seconds=20))

    check(result.exit_code not in (0, None), "exit_code=%r" % (result.exit_code,))
    check(result.ok is False, "a nonzero exit is not ok")
    check(result.reason == orch.R_EXIT_NONZERO, "reason=%r" % (result.reason,))
    check(result.timed_out is False and result.cancelled is False,
          "a nonzero exit must not be misreported as a timeout or cancellation")
    check(result.removed is True and result.removal_verified is True, "cleanup")


# ==========================================================
# F. ENGINE UNAVAILABLE
# ==========================================================

def test_f_engine_unavailable_is_reported_and_not_swallowed():
    """Real CLI failure against a non-existent endpoint - not a mock."""
    broken_env = dict(os.environ)
    broken_env["DOCKER_HOST"] = "npipe:////./pipe/c07b1-does-not-exist"
    orchestrator = orch.BoundedDockerOrchestrator(env=broken_env)

    with pytest.raises(orch.OrchestrationRefused) as info:
        orchestrator.run(orch.ContainerSpec("ubuntu-22.04", "echo_ok", deadline_seconds=10))

    check(info.value.reason == orch.R_ENGINE_UNAVAILABLE,
          "expected engine_unavailable, got %r (%s)" % (info.value.reason, info.value.detail))


# ==========================================================
# G. CANCELLATION BEFORE COMPLETION
# ==========================================================

@needs_engine
def test_g_cancellation_is_distinct_from_a_timeout():
    orchestrator = orch.BoundedDockerOrchestrator()
    timer = threading.Timer(1.0, orchestrator.cancel)
    timer.start()
    try:
        result = orchestrator.run(orch.ContainerSpec(
            "ubuntu-22.04", "sleep_long", deadline_seconds=30, grace_seconds=1))
    finally:
        timer.cancel()

    check(result.cancelled is True, "must report cancellation")
    check(result.timed_out is False,
          "cancellation must not be reported as a deadline breach")
    check(result.reason == orch.R_CANCELLED, "reason=%r" % (result.reason,))
    check(result.duration_seconds < 20,
          "cancellation was not prompt: %r" % (result.duration_seconds,))
    check(result.removed is True and result.removal_verified is True, "cleanup")


# ==========================================================
# H. CLEANUP AFTER AN EXCEPTION
# ==========================================================

@needs_engine
def test_h_cleanup_survives_an_exception_mid_run():
    orchestrator = orch.BoundedDockerOrchestrator()

    def boom():
        raise RuntimeError("injected fault after start")

    with pytest.raises(RuntimeError):
        orchestrator.run(
            orch.ContainerSpec("ubuntu-22.04", "sleep_long", deadline_seconds=30),
            _fault_after_start=boom)

    check(leftover_task_containers(orchestrator) == [],
          "a fault mid-run left a container behind: %r"
          % (leftover_task_containers(orchestrator),))


# ==========================================================
# I. A DIFFERENT IMAGE IS REFUSED
# ==========================================================

def test_i_any_other_image_is_refused():
    for image_key in ("postgres:15", "architectos-api:latest", "python-3.10",
                      "ubuntu:22.04", "nginx:alpine", "", "docker.io/library/ubuntu"):
        with pytest.raises(orch.OrchestrationRefused) as info:
            orch.ContainerSpec(image_key=image_key, command_id="echo_ok")
        check(info.value.reason == orch.R_IMAGE_NOT_APPROVED,
              "image_key=%r got %r" % (image_key, info.value.reason))


# ==========================================================
# J. NETWORK / MOUNT / PRIVILEGED ARE REFUSED
# ==========================================================

def test_j_network_mount_and_privilege_options_are_refused():
    attempts = [
        {"network": "bridge"},
        {"network_mode": "host"},
        {"mounts": ["C:/:/host"]},
        {"mount": "/var/run/docker.sock"},
        {"privileged": True},
        {"host_path": "<repo-root>"},
        {"docker_socket": "/var/run/docker.sock"},
        {"volume": "architectos_pgdata"},
        {"cap_add": "ALL"},
        {"user": "0"},
        {"env": {"POSTGRES_PASSWORD": "x"}},
    ]
    for extra in attempts:
        request = {"image_key": "ubuntu-22.04", "command_id": "echo_ok"}
        request.update(extra)
        with pytest.raises(orch.OrchestrationRefused) as info:
            orch.ContainerSpec.from_request(request)
        check(info.value.reason == orch.R_FORBIDDEN_FIELD,
              "%r got %r" % (extra, info.value.reason))


# ==========================================================
# K. A MODEL-SUPPLIED COMMAND IS REJECTED
# ==========================================================

def test_k_model_supplied_commands_are_rejected():
    # 1. argv smuggled as a field
    with pytest.raises(orch.OrchestrationRefused) as info:
        orch.ContainerSpec.from_request({
            "image_key": "ubuntu-22.04",
            "command_id": "echo_ok",
            "argv": ["rm", "-rf", "/"],
        })
    check(info.value.reason == orch.R_FORBIDDEN_FIELD, info.value.reason)

    # 2. a command string used as a command id
    for command_id in ("rm -rf /", "/bin/sh", "bash -c id", "curl http://example.com",
                       "python -c 'print(1)'", "sh", "echo_ok; rm -rf /"):
        with pytest.raises(orch.OrchestrationRefused) as info:
            orch.ContainerSpec(image_key="ubuntu-22.04", command_id=command_id)
        check(info.value.reason == orch.R_COMMAND_NOT_APPROVED,
              "command_id=%r got %r" % (command_id, info.value.reason))

    # 3. the allowlist is closed: every approved id maps to a fixed tuple
    for command_id, argv in orch.APPROVED_COMMANDS.items():
        check(isinstance(argv, tuple) and argv,
              "approved command %r must be a non-empty tuple" % (command_id,))
        check(all(isinstance(part, str) for part in argv),
              "approved command %r must be all strings" % (command_id,))


# ==========================================================
# L. CANNOT TARGET PRE-EXISTING CONTAINERS
# ==========================================================

@needs_engine
def test_l_cannot_target_preexisting_containers():
    orchestrator = orch.BoundedDockerOrchestrator()
    before = snapshot_containers(orchestrator)
    check(any("architectos_db" in row for row in before),
          "expected the pre-existing architectos_db to be present for this test")

    for field in ("container_id", "container_name", "target"):
        request = {"image_key": "ubuntu-22.04", "command_id": "echo_ok", field: "architectos_db"}
        with pytest.raises(orch.OrchestrationRefused) as info:
            orch.ContainerSpec.from_request(request)
        check(info.value.reason == orch.R_FORBIDDEN_FIELD,
              "field=%r got %r" % (field, info.value.reason))

    # A legitimate run must not disturb anything that already existed.
    result = orchestrator.run(orch.ContainerSpec(
        "ubuntu-22.04", "echo_ok", deadline_seconds=20))
    check(result.removed is True and result.removal_verified is True, "cleanup")

    after = snapshot_containers(orchestrator)
    check(before == after,
          "pre-existing containers changed:\n before=%r\n after=%r" % (before, after))


# ==========================================================
# STRUCTURAL PROOF — no shell, no string commands
# ==========================================================

def test_subprocess_is_always_called_with_an_argument_list():
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    calls = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("run", "Popen", "call", "check_output", "check_call"):
                calls += 1
                first = node.args[0] if node.args else None
                check(isinstance(first, (ast.List, ast.BinOp)),
                      "subprocess.%s received %s; it must be a literal argument list"
                      % (node.func.attr, type(first).__name__))
                for keyword in node.keywords:
                    check(keyword.arg != "shell",
                          "shell= must never be passed to subprocess")
    check(calls >= 2, "expected at least two subprocess calls, found %d" % calls)


def test_no_shell_keyword_in_executable_code():
    with open(MODULE_PATH, "rb") as handle:
        tokens = [t for t in tokenize.tokenize(handle.readline)
                  if t.type not in _NON_CODE_TOKENS]
    text = " ".join(t.string for t in tokens)
    check("shell" not in text,
          "the token 'shell' appears in executable code; commands must be argv lists")


def test_no_dynamic_string_command_construction():
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    for node in ast.walk(tree):
        check(not isinstance(node, ast.JoinedStr),
              "an f-string is present; docker arguments must never be interpolated")


def test_boundary_description_is_honest():
    described = orch.describe_boundary()
    check(described["executes_generated_code"] is False, "must not claim execution")
    check(described["accepts_argv_from_caller"] is False, "argv must not be caller-supplied")
    check(described["accepts_image_reference_from_caller"] is False,
          "image references must not be caller-supplied")
    check(described["uses_shell"] is False, "must not use a shell")
    check(described["exposes_routes"] == [], "must expose no routes")
    check("ubuntu-22.04" in described["approved_images"], "allowlist must be visible")


def test_orchestrator_is_not_imported_by_production():
    offenders = []
    for base in ("core", "ui"):
        root = os.path.join(ROOT, base)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "node_modules")]
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                path = os.path.join(dirpath, filename)
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as handle:
                        text = handle.read()
                except OSError:
                    continue
                if "bounded_docker_orchestrator" in text:
                    offenders.append(os.path.relpath(path, ROOT))
    check(not offenders, "orchestrator reachable from production: %s" % (offenders,))


def test_execution_contract_remains_disabled():
    check(ec.EXECUTION_ENABLED is False,
          "EXECUTION_ENABLED must remain False throughout CODER-07B.1")
    described = ec.describe_contract()
    check(described["executes_anything"] is False, "contract must not claim execution")
    check(described["exposes_routes"] == [], "contract must expose no routes")


# ==========================================================
# FINAL RECONCILIATION — keep last in this file
# ==========================================================

@needs_engine
def test_zz_no_task_containers_remain():
    orchestrator = orch.BoundedDockerOrchestrator()
    leftover = leftover_task_containers(orchestrator)
    check(leftover == [], "task containers left behind: %r" % (leftover,))
