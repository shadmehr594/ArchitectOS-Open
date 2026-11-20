"""CODER-07B.0 — backend gate guards.

C07B.0 activates and evaluates an EXTERNAL isolation backend (Docker Desktop).
It must not, while doing so, wire the execution contract into production, flip
the default-off gate, or make Docker reachable as an execution mechanism.

These tests are pure and offline. Nothing is started, no container is created,
no model is called, no host process is launched.

Scope note: this file asserts ABSENCE of capability. Absence assertions are
dangerous when the detector is broken, so `test_detector_is_not_vacuous` proves
each detector fires on a sample that genuinely contains the pattern — and, just
as important, does NOT fire on a look-alike that does not.
"""

import ast
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.execution import execution_contract_v1 as ec  # noqa: E402

MODULE_REL = os.path.join("core", "execution", "execution_contract_v1.py")
MODULE_ABS = os.path.join(ROOT, MODULE_REL)

CONTRACT_NAMES = ("execution_contract_v1", "core.execution.execution_contract_v1")


def check(condition, message):
    """Raise, never silently pass."""
    if not condition:
        raise AssertionError(message)


def production_files():
    """Every Python file that could serve a request. Excludes the contract
    module itself; tests/ is outside the roots walked here."""
    found = []
    app = os.path.join(ROOT, "app.py")
    if os.path.isfile(app):
        found.append(app)
    for root in ("core", "ui"):
        base = os.path.join(ROOT, root)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames
                           if d not in ("__pycache__", "node_modules", ".git")]
            for filename in filenames:
                if filename.endswith(".py"):
                    found.append(os.path.join(dirpath, filename))
    return [p for p in found if os.path.abspath(p) != os.path.abspath(MODULE_ABS)]


def _parse(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        try:
            return ast.parse(handle.read())
        except SyntaxError:
            return None


def imported_modules(path):
    tree = _parse(path)
    if tree is None:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.add(module)
            for alias in node.names:
                names.add(module + "." + alias.name)
    return names


def _attr_chain(node):
    """Render `a.b.c` as a string, or None if the base is not a plain name."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    else:
        return None
    return ".".join(reversed(parts))


def docker_usage(path):
    """Docker SDK references, found by AST.

    Deliberately NOT a text search: a bare token such as `from_env(` also matches
    this project's own `ChatConfig.from_env()` / `VisionConfig.from_env()`
    config loaders, which have nothing to do with Docker. That false positive
    was observed and is pinned by the self-check below.
    """
    tree = _parse(path)
    if tree is None:
        return []
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "docker" or alias.name.startswith("docker."):
                    found.append("import " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "docker" or node.module.startswith("docker."):
                found.append("from " + node.module)
        elif isinstance(node, ast.Attribute):
            chain = _attr_chain(node)
            if chain is None:
                continue
            if chain.startswith("docker."):
                found.append(chain)
            elif chain == "containers.run" or chain.endswith(".containers.run"):
                found.append(chain)
    return sorted(set(found))


# ==========================================================
# THE GATE IS STILL OFF
# ==========================================================

def test_execution_enabled_is_still_false():
    check(ec.EXECUTION_ENABLED is False,
          "EXECUTION_ENABLED must remain False throughout C07B.0")


def test_authorize_still_refuses_a_well_formed_request():
    """Even a fully valid request is refused, because the flag is off."""
    source = "def add(a, b):\n    return a + b\n"
    digest = ec.sha256_text(source)
    now = 1_000_000.0
    request = {
        "project_id": "project_test",
        "artifact_id": "documents/code/calculator.py",
        "source_sha256": digest,
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
    authorization = {
        "source": "user",
        "scope": ec.SCOPE_EXECUTE,
        "project_id": "project_test",
        "session_id": "lss_test_session",
        "source_sha256": digest,
        "expires_at": now + 300,
        "consumed": False,
    }
    outcome = ec.authorize_execution(
        request, authorization,
        source_text=source, now=now, bound_session_id="lss_test_session",
    )
    check(outcome["allowed"] is False, "authorize_execution must refuse in C07B.0")
    check(outcome["reason"] == ec.R_EXECUTION_DISABLED,
          "expected execution_disabled, got %r" % (outcome["reason"],))


def test_contract_still_claims_no_execution_capability():
    described = ec.describe_contract()
    check(described["executes_anything"] is False, "contract must not claim execution")
    check(described["exposes_routes"] == [], "contract must expose no routes")
    check(described["execution_enabled"] is False, "execution must be disabled")


# ==========================================================
# THE CONTRACT IS STILL DISCONNECTED FROM PRODUCTION
# ==========================================================

def test_contract_module_is_not_imported_by_any_production_file():
    offenders = []
    for path in production_files():
        for name in imported_modules(path):
            if name in CONTRACT_NAMES or name.endswith(".execution_contract_v1"):
                offenders.append(os.path.relpath(path, ROOT))
                break
    check(not offenders,
          "execution contract must stay disconnected, imported by: %s" % (offenders,))


def test_no_execution_route_was_added():
    candidates = [os.path.join(ROOT, "app.py"), os.path.join(ROOT, "ui", "app.py")]
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


def test_no_docker_execution_api_in_production():
    """Docker must not be reachable from the product as an execution mechanism."""
    offenders = []
    for path in production_files():
        for ref in docker_usage(path):
            offenders.append((os.path.relpath(path, ROOT), ref))
    check(not offenders, "docker SDK reachable from production: %s" % (offenders,))


# ==========================================================
# DETECTOR SELF-CHECK — absence tests must be able to fail
# ==========================================================

def test_detector_is_not_vacuous(tmp_path):
    wired = tmp_path / "wired.py"
    wired.write_text(
        "from core.execution.execution_contract_v1 import authorize_execution\n"
        "import docker\n"
        "client = docker.from_env()\n"
        "client.containers.run('img')\n",
        encoding="utf-8",
    )
    names = imported_modules(str(wired))
    check(any(n in CONTRACT_NAMES for n in names),
          "import detector failed to see a real contract import: %s" % (sorted(names),))

    refs = docker_usage(str(wired))
    check(any(r.startswith("import docker") for r in refs),
          "docker detector missed a real import: %s" % (refs,))
    check(any("containers.run" in r for r in refs),
          "docker detector missed a real execution call: %s" % (refs,))

    # The exact false positive observed on the first run of this suite: a
    # project config loader must never be reported as Docker usage.
    lookalike = tmp_path / "lookalike.py"
    lookalike.write_text(
        "from config.chat_config import ChatConfig\n"
        "cfg = ChatConfig.from_env()\n"
        "other = VisionConfig.from_env(model='x')\n",
        encoding="utf-8",
    )
    check(docker_usage(str(lookalike)) == [],
          "detector must not report Config.from_env() as docker: %s"
          % (docker_usage(str(lookalike)),))
