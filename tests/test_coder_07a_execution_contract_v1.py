"""CODER-07A — execution contract: fail-closed negative controls.

Every test here is OFFLINE and PURE. Nothing is executed, no container or VM is
started, no model is called, no host process is launched.

Two distinct claims are proven, and they must not be confused:

  1. validate_execution_request() refuses each specific missing protection with
     a SPECIFIC reason code. This proves the individual controls exist and are
     not a single blanket refusal.
  2. authorize_execution() refuses EVERYTHING with execution_disabled while
     EXECUTION_ENABLED is False. This proves the authority is off by default.

A positive control (test_valid_request_would_pass_validation) proves the
validator is not trivially refusing all input — without it, the twelve negative
tests would be vacuous.
"""

import ast
import os
import sys
import tokenize

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.execution import execution_contract_v1 as ec  # noqa: E402

MODULE_PATH = os.path.join(ROOT, "core", "execution", "execution_contract_v1.py")

# Token classes that carry no executable meaning. Dropping them means the
# structural scan reads code, not prose.
_NON_CODE_TOKENS = frozenset({
    tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE,
    tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING, tokenize.ENDMARKER,
})

SOURCE = "def add(a, b):\n    return a + b\n"
DIGEST = ec.sha256_text(SOURCE)
NOW = 1_000_000.0
SESSION = "lss_test_session"
PROJECT = "project_test"


def check(condition, message):
    """Raise, never silently pass — a swallowed failure is worse than a red test."""
    if not condition:
        raise AssertionError(message)


def valid_request(**overrides):
    request = {
        "project_id": PROJECT,
        "artifact_id": "documents/code/calculator.py",
        "source_sha256": DIGEST,
        "interpreter": "python3.12",
        "backend_kind": ec.BACKEND_RESTRICTED_CONTAINER,
        # C07B.2 §8 tightened the contract: naming an isolation class is not
        # evidence that one was verified, so the evidence class is now required.
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
        # C07B.2 §8: `source: "user"` is a self-description, not proof of who
        # issued the capability. The issuer is now a required binding.
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
# STRUCTURAL PROOF — there is no executor in this module
# ==========================================================

def test_module_has_no_process_or_shell_capability():
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        source = handle.read()
    tree = ast.parse(source)

    forbidden_modules = {"subprocess", "shutil", "pty", "multiprocessing", "ctypes"}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    check(not (imported & forbidden_modules),
          "forbidden imports present: %s" % (imported & forbidden_modules))

    # os.system / os.exec* / os.spawn* would require importing os at all.
    check("os" not in imported, "module imports os; os.system/exec must stay unreachable")

    # Second layer: scan CODE ONLY. Comments, docstrings and every other string
    # literal are dropped by the tokenizer first, so the module's own prose
    # ("A host subprocess ... is NOT a security boundary") cannot trip the check.
    # A raw-text scan over the whole file is a HARNESS defect: it reports a
    # product violation that does not exist, and it would equally hide a real
    # one behind a harmless comment.
    code_only = []
    with open(MODULE_PATH, "rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type in _NON_CODE_TOKENS:
                continue
            code_only.append(token.string)
    code_text = " ".join(code_only)

    for needle in ("subprocess", "Popen", "popen", "os.system", "os.exec",
                   "os.spawn", "ctypes", "shell"):
        check(needle not in code_text,
              "forbidden token present in executable code: %s" % needle)

    # Third layer: no call may request a host shell or a substituted executable.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                check(keyword.arg not in ("shell", "executable"),
                      "forbidden call keyword: %s" % keyword.arg)


def test_structural_scanner_is_not_vacuous(tmp_path):
    """Harness self-check: the code-only scan must CATCH a real violation.

    Without this, the structural test above could pass simply because the
    scanner never looks at anything. It also pins the distinction that caused
    one false failure: the same word in a docstring must NOT be reported.
    """
    clean = tmp_path / "clean.py"
    clean.write_text(
        '"""This docstring may mention subprocess and shell=True freely."""\n'
        "import hashlib\n"
        "def f():\n"
        "    return hashlib.sha256(b'x')\n",
        encoding="utf-8",
    )
    dirty = tmp_path / "dirty.py"
    dirty.write_text(
        "import subprocess\n"
        "def f():\n"
        "    return subprocess.run(['calc'], shell=True)\n",
        encoding="utf-8",
    )

    def scan(path):
        found = []
        with open(path, "rb") as handle:
            for token in tokenize.tokenize(handle.readline):
                if token.type in _NON_CODE_TOKENS:
                    continue
                found.append(token.string)
        text = " ".join(found)
        return [n for n in ("subprocess", "shell") if n in text]

    check(scan(clean) == [], "prose in a docstring must not be reported: %s" % (scan(clean),))
    check(scan(dirty) == ["subprocess", "shell"],
          "the scanner must catch real code violations, got %s" % (scan(dirty),))


def test_execution_enabled_has_exactly_one_assignment_and_it_is_false():
    with open(MODULE_PATH, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    assignments = []
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "EXECUTION_ENABLED":
                assignments.append(value)

    check(len(assignments) == 1,
          "EXECUTION_ENABLED must be assigned exactly once, found %d" % len(assignments))
    value = assignments[0]
    check(isinstance(value, ast.Constant) and value.value is False,
          "EXECUTION_ENABLED must be the literal False")


def test_no_execution_route_is_exposed():
    """No /execute, /shell or /terminal writable API anywhere in the product."""
    candidates = [
        os.path.join(ROOT, "app.py"),
        os.path.join(ROOT, "ui", "app.py"),
    ]
    routes_dir = os.path.join(ROOT, "ui", "routes")
    if os.path.isdir(routes_dir):
        for name in os.listdir(routes_dir):
            if name.endswith(".py"):
                candidates.append(os.path.join(routes_dir, name))

    offenders = []
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        for needle in ('"/execute"', "'/execute'", '"/shell"', "'/shell'",
                       '"/terminal"', "'/terminal'"):
            if needle in text:
                offenders.append((os.path.basename(path), needle))

    check(not offenders, "execution routes exposed: %s" % (offenders,))


# ==========================================================
# DEFAULT-OFF GATE
# ==========================================================

def test_authorize_execution_is_disabled_by_default():
    outcome = ec.authorize_execution(
        valid_request(), valid_authorization(),
        source_text=SOURCE, now=NOW, bound_session_id=SESSION,
    )
    check(outcome["allowed"] is False, "authorize_execution must refuse in C07A")
    check(outcome["reason"] == ec.R_EXECUTION_DISABLED,
          "expected execution_disabled, got %r" % (outcome["reason"],))


def test_contract_reports_no_execution_capability():
    described = ec.describe_contract()
    check(described["executes_anything"] is False, "contract must not claim execution")
    check(described["exposes_routes"] == [], "contract must expose no routes")
    check(described["execution_enabled"] is False, "execution must be disabled")
    check(ec.SCOPE_EXECUTE not in (ec.SCOPE_SAVE, ec.SCOPE_OVERWRITE),
          "execute scope must be distinct from save/overwrite")


# ==========================================================
# POSITIVE CONTROL — proves the validator is not vacuous
# ==========================================================

def test_valid_request_would_pass_validation():
    outcome = reason_for(valid_request(), valid_authorization())
    check(outcome["allowed"] is True,
          "a fully valid request must validate, got %r" % (outcome["reason"],))


# ==========================================================
# THE TWELVE REQUIRED NEGATIVE CONTROLS
# ==========================================================

def test_01_execution_without_separate_approval_is_refused():
    outcome = reason_for(valid_request(), None)
    check(outcome["allowed"] is False, "must refuse")
    check(outcome["reason"] == ec.R_EXECUTION_AUTHORIZATION_REQUIRED,
          "got %r" % (outcome["reason"],))


def test_02a_expired_execution_approval_is_refused():
    outcome = reason_for(valid_request(), valid_authorization(expires_at=NOW - 1))
    check(outcome["reason"] == ec.R_EXECUTION_AUTHORIZATION_EXPIRED,
          "got %r" % (outcome["reason"],))


def test_02b_replayed_execution_approval_is_refused():
    outcome = reason_for(valid_request(), valid_authorization(consumed=True))
    check(outcome["reason"] == ec.R_EXECUTION_AUTHORIZATION_REPLAYED,
          "got %r" % (outcome["reason"],))


def test_03_source_digest_mismatch_is_refused():
    wrong = "0" * 64
    outcome = reason_for(valid_request(source_sha256=wrong), valid_authorization())
    check(outcome["reason"] == ec.R_SOURCE_DIGEST_MISMATCH,
          "got %r" % (outcome["reason"],))


def test_04_cross_project_request_is_refused():
    outcome = reason_for(valid_request(project_id="project_other"), valid_authorization())
    check(outcome["reason"] == ec.R_PROJECT_BINDING_MISMATCH,
          "got %r" % (outcome["reason"],))


def test_05_cross_session_request_is_refused():
    outcome = reason_for(
        valid_request(), valid_authorization(),
        bound_session_id="lss_a_different_session",
    )
    check(outcome["reason"] == ec.R_SESSION_BINDING_MISMATCH,
          "got %r" % (outcome["reason"],))


def test_06_network_access_without_permission_is_refused():
    for policy in ("bridge", "host", "enabled", "egress", None):
        outcome = reason_for(valid_request(network_policy=policy), valid_authorization())
        check(outcome["reason"] == ec.R_NETWORK_NOT_PERMITTED,
              "policy=%r got %r" % (policy, outcome["reason"]))


def test_07_host_filesystem_mount_is_refused():
    for mounts in ([r"<repo-root>"], ["/mnt/c"], [{"host": "C:/"}]):
        outcome = reason_for(valid_request(mounts=mounts), valid_authorization())
        check(outcome["reason"] == ec.R_HOST_MOUNT_NOT_PERMITTED,
              "mounts=%r got %r" % (mounts, outcome["reason"]))


def test_08_administrator_privileges_are_refused():
    outcome = reason_for(valid_request(privileged=True), valid_authorization())
    check(outcome["reason"] == ec.R_PRIVILEGED_EXECUTION_REFUSED,
          "got %r" % (outcome["reason"],))


def test_09_unbounded_runtime_or_resources_are_refused():
    # missing limits entirely
    outcome = reason_for(valid_request(limits=None), valid_authorization())
    check(outcome["reason"] == ec.R_RESOURCE_LIMIT_INVALID, "missing: got %r" % (outcome["reason"],))

    # a partial limits dict (e.g. no runtime cap) must also fail
    partial = valid_request(limits={"max_memory_mb": 256})
    outcome = reason_for(partial, valid_authorization())
    check(outcome["reason"] == ec.R_RESOURCE_LIMIT_INVALID, "partial: got %r" % (outcome["reason"],))

    # above the ceiling
    over = valid_request()
    over["limits"] = dict(over["limits"], max_runtime_seconds=3600)
    outcome = reason_for(over, valid_authorization())
    check(outcome["reason"] == ec.R_RESOURCE_LIMIT_INVALID, "over: got %r" % (outcome["reason"],))

    # explicitly unbounded / non-positive
    zero = valid_request()
    zero["limits"] = dict(zero["limits"], max_output_bytes=0)
    outcome = reason_for(zero, valid_authorization())
    check(outcome["reason"] == ec.R_RESOURCE_LIMIT_INVALID, "zero: got %r" % (outcome["reason"],))


def test_10_source_changed_after_approval_is_refused():
    tampered = SOURCE + "\nimport os\nos.system('calc')\n"
    outcome = reason_for(valid_request(), valid_authorization(), source_text=tampered)
    check(outcome["reason"] == ec.R_SOURCE_CHANGED_AFTER_APPROVAL,
          "got %r" % (outcome["reason"],))


def test_11_arbitrary_command_execution_is_refused():
    # a host shell instead of the allowlisted interpreter
    for interpreter in ("cmd.exe", "powershell", "pwsh", "C:\\Windows\\System32\\cmd.exe",
                        "/bin/sh", "bash"):
        outcome = reason_for(valid_request(interpreter=interpreter), valid_authorization())
        check(outcome["reason"] == ec.R_ARBITRARY_COMMAND_REFUSED,
              "interpreter=%r got %r" % (interpreter, outcome["reason"]))

    # shell metacharacters smuggled through argv
    for argv in (["&&", "calc"], ["; rm -rf /"], ["|", "more"], ["$(whoami)"],
                 ["..\\..\\Windows\\System32\\cmd.exe"]):
        outcome = reason_for(valid_request(argv=argv), valid_authorization())
        check(outcome["reason"] == ec.R_ARBITRARY_COMMAND_REFUSED,
              "argv=%r got %r" % (argv, outcome["reason"]))


def test_12_model_generated_text_claiming_permission_is_refused():
    for source in ("model", "assistant", "llm", "system", None):
        outcome = reason_for(valid_request(), valid_authorization(source=source))
        check(outcome["reason"] == ec.R_APPROVAL_SOURCE_MUST_BE_USER,
              "source=%r got %r" % (source, outcome["reason"]))


# ==========================================================
# SCOPE SEPARATION — save authority is not execute authority
# ==========================================================

def test_save_scope_capability_cannot_authorize_execution():
    for scope in (ec.SCOPE_SAVE, ec.SCOPE_OVERWRITE, "read", None):
        outcome = reason_for(valid_request(), valid_authorization(scope=scope))
        check(outcome["reason"] == ec.R_EXECUTION_SCOPE_MISMATCH,
              "scope=%r got %r" % (scope, outcome["reason"]))


# ==========================================================
# BACKEND CLASS — a host process is never a boundary
# ==========================================================

def test_non_boundary_backend_classes_are_refused():
    for backend in ("host_process", "subprocess_timeout_only", "wsl_direct",
                    "unrestricted_container", "whatever", None):
        outcome = reason_for(valid_request(backend_kind=backend), valid_authorization())
        check(outcome["reason"] == ec.R_BACKEND_NOT_APPROVED,
              "backend=%r got %r" % (backend, outcome["reason"]))


def test_preview_executes_nothing():
    preview = ec.build_execution_preview(valid_request(), source_text=SOURCE)
    check(preview["executed"] is False, "preview must never execute")
    check(preview["preview_only"] is True, "preview must be marked preview_only")
    check(preview["execution_enabled"] is False, "preview must report execution disabled")
