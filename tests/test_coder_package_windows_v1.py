# -*- coding: utf-8 -*-
"""CODER — Windows EXE packaging (sandbox only).

These are OFFLINE tests. They never start Windows Sandbox, never run
PyInstaller, and never execute generated code. The sandbox itself is exercised
by the human acceptance step; what is proven here is the host-side contract:
digest binding, path safety, manifest verification, and the absence of any
host build path.
"""

import ast
import io
import json
import os
import sys
import tokenize

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.execution.packaging import windows_package_v1 as wp  # noqa: E402

MODULE_PATH = os.path.join(
    ROOT, "core", "execution", "packaging", "windows_package_v1.py")
BUILD_SCRIPT_PATH = os.path.join(
    ROOT, "core", "execution", "packaging", "assets", "build_sandbox.ps1")

_NON_CODE = frozenset({
    tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE,
    tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING, tokenize.ENDMARKER,
})


def _code_tokens(path):
    with open(path, "rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type not in _NON_CODE:
                yield token


def _trusted(*_a, **_k):
    return {"trusted": True, "actor_id": "actor", "session_id": "session"}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Isolated job root, project code root and fake toolchain."""
    python_home = tmp_path / "pyhome"
    python_home.mkdir()
    (python_home / "python.exe").write_bytes(b"MZ")
    site = tmp_path / "site-packages"
    site.mkdir()
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    code_root = tmp_path / "code"
    code_root.mkdir()

    monkeypatch.setattr(wp, "JOBS_ROOT", jobs)
    monkeypatch.setattr(wp, "PYTHON_HOME", python_home)
    monkeypatch.setattr(wp, "TOOLCHAIN_SITE", site)
    monkeypatch.setattr(wp, "_project_code_root", lambda pid: code_root)
    monkeypatch.setattr(wp, "verify_proxy_request", _trusted)
    monkeypatch.setenv(wp.OPT_IN_ENV, "1")
    return {"jobs": jobs, "code_root": code_root, "python_home": python_home,
            "site": site}


def _prepare(payload=None, **overrides):
    body = {
        "operation": "prepare_package",
        "project_id": "project_test",
        "filename": "app.py",
        "confirm_package": True,
    }
    body.update(payload or {})
    kwargs = {
        "proxy_secret": "x" * 40,
        "headers": {},
        "payload": body,
        "path": wp.PREPARE_PATH,
        "remote_addr": "127.0.0.1",
        "nonce_ledger": None,
        "now": 1_000_000,
    }
    kwargs.update(overrides)
    return wp.prepare_package(**kwargs)


def _status(payload=None, **overrides):
    body = {"operation": "package_status", "project_id": "project_test",
            "job_id": "0" * 16}
    body.update(payload or {})
    kwargs = {
        "proxy_secret": "x" * 40,
        "headers": {},
        "payload": body,
        "path": wp.STATUS_PATH,
        "remote_addr": "127.0.0.1",
        "nonce_ledger": None,
        "now": 1_000_000,
    }
    kwargs.update(overrides)
    return wp.package_status(**kwargs)


# -- declared posture ---------------------------------------------------
def test_packager_is_disabled_by_default():
    assert wp.describe_packager()["default_enabled"] is False
    assert wp.packager_enabled({}) is False
    assert wp.packager_enabled({wp.OPT_IN_ENV: "1"}) is True


def test_packager_declares_no_host_build():
    described = wp.describe_packager()
    assert described["host_build_available"] is False
    assert described["host_executes_generated_code"] is False
    assert described["sandbox_network"] == "disabled"
    assert described["builder"] == "windows_sandbox"
    assert described["separate_from_save"] is True
    assert described["separate_from_run"] is True


def test_module_has_no_host_build_machinery():
    """The host module must not be able to run a build itself."""
    forbidden = {"subprocess", "PyInstaller", "pyinstaller", "multiprocessing"}
    imported = set()
    for node in ast.walk(ast.parse(open(MODULE_PATH, encoding="utf-8").read())):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not (imported & forbidden), "host build machinery present: %s" % (
        imported & forbidden,)

    text = " ".join(tok.string for tok in _code_tokens(MODULE_PATH))
    for needle in ("os.system", "Popen", "check_output", "check_call", "run("):
        assert needle not in text, "host command execution present: %s" % needle


# -- build script must not run PyInstaller from System32 ----------------
def test_build_script_cannot_invoke_pyinstaller_from_system32():
    """Regression: the logon command's cwd is C:\\Windows\\system32.

    PyInstaller refuses to run from there, which is exactly how the first
    sandbox smoke test failed. The script must change into the writable output
    folder first, and every artefact path must stay inside it.
    """
    with open(BUILD_SCRIPT_PATH, encoding="utf-8") as handle:
        text = handle.read()

    assert "$Out = 'C:\\pkg\\out'" in text, "output folder is not C:\\pkg\\out"

    set_loc = text.find("Set-Location -LiteralPath $Out")
    invocation = text.find("-m PyInstaller")
    assert set_loc != -1, "build script never changes the working directory"
    assert invocation != -1, "build script does not invoke PyInstaller"
    assert set_loc < invocation, (
        "Set-Location must run BEFORE the PyInstaller invocation")

    # every artefact path stays inside the writable output folder
    for name in ("dist", "work", "spec"):
        assert "Join-Path $Out '%s'" % name in text, (
            "%s path is not inside the output folder" % name)

    # no directory change targets a fixed system path
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Set-Location"):
            assert "$Out" in stripped, (
                "Set-Location must target the output folder: %r" % stripped)


# -- consent and opt-in -------------------------------------------------
def test_prepare_refuses_when_disabled(env, monkeypatch):
    monkeypatch.delenv(wp.OPT_IN_ENV, raising=False)
    result = _prepare()
    assert result["ok"] is False
    assert result["reason"] == "packaging_disabled"
    assert list(env["jobs"].iterdir()) == []


def test_prepare_requires_explicit_confirmation(env):
    result = _prepare({"confirm_package": False})
    assert result["ok"] is False
    assert result["reason"] == "explicit_package_confirmation_required"
    assert list(env["jobs"].iterdir()) == []


def test_prepare_refuses_untrusted_proxy(env, monkeypatch):
    monkeypatch.setattr(
        wp, "verify_proxy_request",
        lambda *a, **k: {"trusted": False, "reason": "proxy_signature_invalid"})
    result = _prepare()
    assert result["ok"] is False
    assert result["reason"] == "proxy_signature_invalid"
    assert list(env["jobs"].iterdir()) == []


def test_prepare_refuses_unknown_fields(env):
    result = _prepare({"extra": "x"})
    assert result["ok"] is False
    assert result["reason"] == "packaging_payload_invalid"


def test_prepare_refuses_missing_source(env):
    result = _prepare()
    assert result["ok"] is False
    assert result["reason"] == "saved_python_artifact_unavailable"


# -- staging ------------------------------------------------------------
def test_prepare_stages_exact_bytes_and_digest(env):
    source = b'print("hello from architectos")\n'
    (env["code_root"] / "app.py").write_bytes(source)

    result = _prepare()
    assert result["ok"] is True
    assert result["stage"] == "awaiting_sandbox"
    assert result["source_sha256"] == wp._sha256_bytes(source)
    assert result["manual_launch_required"] is True
    assert result["host_build_available"] is False

    job_dir = env["jobs"] / result["job_id"]
    assert (job_dir / "input" / "source.py").read_bytes() == source
    job = json.loads((job_dir / "input" / "job.json").read_text())
    assert job["source_sha256"] == wp._sha256_bytes(source)
    assert job["exe_name"] == result["exe_name"]


def test_wsb_disables_network_and_mounts_read_only(env):
    (env["code_root"] / "app.py").write_bytes(b"print(1)\n")
    result = _prepare()
    wsb = (env["jobs"] / result["job_id"] / "package.wsb").read_text()

    assert "<Networking>Disable</Networking>" in wsb
    assert "<ClipboardRedirection>Disable</ClipboardRedirection>" in wsb
    assert "<PrinterRedirection>Disable</PrinterRedirection>" in wsb
    assert wsb.count("<ReadOnly>true</ReadOnly>") == 3
    assert wsb.count("<ReadOnly>false</ReadOnly>") == 1
    # the only writable mount is the job output folder
    assert result["output_dir"].replace("\\", "/") in wsb.replace("\\", "/")
    # no unrelated host folder is exposed
    assert "Docker" not in wsb and "docker" not in wsb
    assert ".venv" not in wsb


def test_exe_name_is_path_free():
    # basename is taken first, so a directory component can never survive
    assert wp.exe_name_for("../../evil.py") == "ArchitectOS_evil"
    assert wp.exe_name_for("a b/c.py") == "ArchitectOS_c"
    assert wp.exe_name_for("my app.py") == "ArchitectOS_my_app"
    assert wp.exe_name_for("").startswith("ArchitectOS_")
    assert "/" not in wp.exe_name_for("x/y.py")
    assert "\\" not in wp.exe_name_for("x\\y.py")


def test_job_dir_rejects_traversal(env):
    assert wp._job_dir("../../etc") is None
    assert wp._job_dir("not-a-job-id") is None
    assert wp._job_dir("0" * 16) is not None


# -- status / verification ---------------------------------------------
def _deliverable_job(env, exe_bytes=b"MZ-fake-exe"):
    (env["code_root"] / "app.py").write_bytes(b"print(1)\n")
    prepared = _prepare()
    job_dir = env["jobs"] / prepared["job_id"]
    dist = job_dir / "output" / "dist"
    dist.mkdir(parents=True)
    exe = dist / (prepared["exe_name"] + ".exe")
    exe.write_bytes(exe_bytes)
    return prepared, job_dir, exe


def _write_manifest(job_dir, prepared, exe, **overrides):
    manifest = {
        "contract": wp.SANDBOX_BUILD_CONTRACT,
        "job_id": prepared["job_id"],
        "source_sha256": prepared["source_sha256"],
        "exe_name": prepared["exe_name"],
        "status": "ok",
        "exit_code": 0,
        "exe_sha256": wp._sha256_file(exe),
        "exe_size": exe.stat().st_size,
        "finished_at": "2026-10-25T00:00:00Z",
    }
    manifest.update(overrides)
    (job_dir / "output" / "manifest.json").write_text(json.dumps(manifest))
    return manifest


def test_status_before_build_reports_awaiting_sandbox(env):
    (env["code_root"] / "app.py").write_bytes(b"print(1)\n")
    prepared = _prepare()
    result = _status({"job_id": prepared["job_id"]})
    assert result["ok"] is True
    assert result["stage"] == "awaiting_sandbox"
    assert result["manual_launch_required"] is True


# -- PowerShell 5.1 writes a UTF-8 BOM ---------------------------------
def test_read_manifest_accepts_utf8_bom(env):
    """`Set-Content -Encoding utf8` on PS 5.1 prefixes a BOM."""
    (env["code_root"] / "app.py").write_bytes(b"print(1)\n")
    prepared = _prepare()
    job_dir = env["jobs"] / prepared["job_id"]
    (job_dir / "output").mkdir(parents=True, exist_ok=True)

    body = json.dumps({
        "contract": wp.SANDBOX_BUILD_CONTRACT,
        "job_id": prepared["job_id"],
        "status": "ok",
    })
    manifest_path = job_dir / "output" / "manifest.json"
    manifest_path.write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8"))
    assert manifest_path.read_bytes().startswith(b"\xef\xbb\xbf")

    parsed = wp._read_manifest(job_dir)
    assert parsed is not None
    assert parsed["status"] == "ok"
    assert parsed["job_id"] == prepared["job_id"]


def test_status_delivers_with_bom_manifest(env):
    """A BOM must not break verification or delivery."""
    prepared, job_dir, exe = _deliverable_job(env)
    manifest = {
        "contract": wp.SANDBOX_BUILD_CONTRACT,
        "job_id": prepared["job_id"],
        "source_sha256": prepared["source_sha256"],
        "exe_name": prepared["exe_name"],
        "status": "ok",
        "exit_code": 0,
        "exe_sha256": wp._sha256_file(exe),
        "exe_size": exe.stat().st_size,
    }
    payload = json.dumps(manifest).encode("utf-8")
    (job_dir / "output" / "manifest.json").write_bytes(b"\xef\xbb\xbf" + payload)

    result = _status({"job_id": prepared["job_id"]})
    assert result["ok"] is True, result
    assert result["stage"] == "delivered"
    assert result["exe_sha256"] == wp._sha256_file(exe)


def test_manifest_without_bom_still_reads(env):
    """utf-8-sig must stay byte-compatible with a plain UTF-8 manifest."""
    (env["code_root"] / "app.py").write_bytes(b"print(1)\n")
    prepared = _prepare()
    job_dir = env["jobs"] / prepared["job_id"]
    (job_dir / "output").mkdir(parents=True, exist_ok=True)
    (job_dir / "output" / "manifest.json").write_bytes(
        json.dumps({"contract": wp.SANDBOX_BUILD_CONTRACT,
                    "job_id": prepared["job_id"],
                    "status": "ok"}).encode("utf-8"))
    parsed = wp._read_manifest(job_dir)
    assert parsed["status"] == "ok"


def test_status_delivers_verified_exe(env):
    prepared, job_dir, exe = _deliverable_job(env)
    _write_manifest(job_dir, prepared, exe)

    result = _status({"job_id": prepared["job_id"]})
    assert result["ok"] is True, result
    assert result["stage"] == "delivered"
    assert result["exe_sha256"] == wp._sha256_file(exe)
    assert result["artifact_url"].startswith(
        "/artifacts/project_media/project_test/documents/code/dist/")
    delivered = env["code_root"] / "dist" / (prepared["exe_name"] + ".exe")
    assert delivered.is_file()
    assert delivered.read_bytes() == exe.read_bytes()


def test_status_rejects_exe_digest_mismatch(env):
    prepared, job_dir, exe = _deliverable_job(env)
    _write_manifest(job_dir, prepared, exe, exe_sha256="0" * 64)
    result = _status({"job_id": prepared["job_id"]})
    assert result["ok"] is False
    assert result["reason"] == "packaging_exe_digest_mismatch"


def test_status_rejects_source_mismatch(env):
    prepared, job_dir, exe = _deliverable_job(env)
    _write_manifest(job_dir, prepared, exe, source_sha256="1" * 64)
    result = _status({"job_id": prepared["job_id"]})
    assert result["ok"] is False
    assert result["reason"] == "packaging_manifest_source_mismatch"


def test_status_rejects_job_mismatch(env):
    prepared, job_dir, exe = _deliverable_job(env)
    _write_manifest(job_dir, prepared, exe, job_id="f" * 16)
    result = _status({"job_id": prepared["job_id"]})
    assert result["ok"] is False
    assert result["reason"] == "packaging_manifest_job_mismatch"


def test_status_rejects_failed_build(env):
    prepared, job_dir, exe = _deliverable_job(env)
    _write_manifest(job_dir, prepared, exe, status="build_failed", exit_code=3)
    result = _status({"job_id": prepared["job_id"]})
    assert result["ok"] is False
    assert result["reason"] == "packaging_build_build_failed"


def test_status_rejects_wrong_contract(env):
    prepared, job_dir, exe = _deliverable_job(env)
    _write_manifest(job_dir, prepared, exe, contract="SomethingElse")
    result = _status({"job_id": prepared["job_id"]})
    assert result["ok"] is False
    assert result["reason"] == "packaging_manifest_contract_invalid"


def test_status_rejects_missing_exe(env):
    prepared, job_dir, exe = _deliverable_job(env)
    _write_manifest(job_dir, prepared, exe)
    exe.unlink()
    result = _status({"job_id": prepared["job_id"]})
    assert result["ok"] is False
    assert result["reason"] == "packaging_exe_missing"


def test_status_rejects_other_project(env):
    prepared, job_dir, exe = _deliverable_job(env)
    _write_manifest(job_dir, prepared, exe)
    result = _status({"job_id": prepared["job_id"], "project_id": "project_other"})
    assert result["ok"] is False
    assert result["reason"] == "packaging_job_project_mismatch"


def test_status_refuses_unknown_job(env):
    result = _status({"job_id": "a" * 16})
    assert result["ok"] is False
    assert result["reason"] == "packaging_job_unavailable"
