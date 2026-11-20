# -*- coding: utf-8 -*-
"""ArchitectOS Windows EXE packaging — sandbox-only, fail-closed.

This module never builds on the host. It stages a job for Windows Sandbox,
then reads back a build manifest and delivers the verified artifact.

The split is deliberate:

* the **host** only writes inputs and reads outputs; it never imports, compiles
  or executes the generated program, and it never invokes PyInstaller;
* the **sandbox** runs the fixed, reviewed ``build_sandbox.ps1`` with networking
  disabled and three read-only mappings (source, Python, PyInstaller modules)
  plus one writable output directory.

Packaging is a SEPARATE consent from saving and from running. Saving a file does
not authorise packaging it, and packaging does not authorise running it.

Default state is OFF and requires the server opt-in
``ARCHITECTOS_PACKAGER_ENABLED=1``.
"""

import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import sys
import time
from pathlib import Path

from core.chat.project_code_file_writer_v1 import (
    MAX_CODE_FILE_BYTES,
    validate_code_filename,
    validate_project_id,
)
from core.runtime.local_authorization_v1 import verify_proxy_request

CONTRACT = "ArchitectOSWindowsPackageV1"
VERSION = "1.0"

PREPARE_PATH = "/api/coder/package/prepare"
STATUS_PATH = "/api/coder/package/status"

SCOPE = "package_windows"
ACTION = "build_windows_exe"

OPT_IN_ENV = "ARCHITECTOS_PACKAGER_ENABLED"
AUTOLAUNCH_ENV = "ARCHITECTOS_PACKAGER_AUTOLAUNCH"

SANDBOX_BUILD_CONTRACT = "ArchitectOSSandboxBuildV1"
SANDBOX_EXE = r"C:\Windows\System32\WindowsSandbox.exe"

REPO_ROOT = Path(__file__).resolve().parents[3]
JOBS_ROOT = REPO_ROOT / "runs" / "packaging_jobs"
TOOLCHAIN_SITE = REPO_ROOT / "runs" / "packaging_toolchain" / "site-packages"
ASSETS = Path(__file__).resolve().parent / "assets"
TEMPLATE_PATH = ASSETS / "package_template.wsb"
BUILD_SCRIPT_PATH = ASSETS / "build_sandbox.ps1"

# The base interpreter that carries tkinter. Core runs inside a venv, so
# sys.base_prefix is the underlying full installation.
PYTHON_HOME = Path(sys.base_prefix)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_-]+")
_JOB_ID = re.compile(r"^[0-9a-f]{16}$")

_PREPARE_FIELDS = {"operation", "project_id", "filename", "confirm_package"}
_STATUS_FIELDS = {"operation", "project_id", "job_id"}

MAX_WAIT_SECONDS = 600


def _result(ok, reason=None, **values):
    payload = {
        "contract": CONTRACT,
        "version": VERSION,
        "ok": bool(ok),
        "reason": reason,
    }
    payload.update(values)
    return payload


def packager_enabled(environ=None):
    source = os.environ if environ is None else environ
    return str(source.get(OPT_IN_ENV, "")) == "1"


def _autolaunch_enabled(environ=None):
    source = os.environ if environ is None else environ
    return str(source.get(AUTOLAUNCH_ENV, "")) == "1"


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def exe_name_for(filename):
    """Deterministic, path-free EXE name derived from the saved filename."""
    stem = os.path.splitext(os.path.basename(str(filename or "")))[0]
    cleaned = _SAFE_NAME.sub("_", stem).strip("_")
    if not cleaned:
        cleaned = "ArchitectOS_App"
    return "ArchitectOS_" + cleaned[:48]


def _project_code_root(project_id):
    from core.project.project_workspace_v1 import project_workspace

    if not project_workspace.exists(project_id):
        raise ValueError("project_not_found")
    return Path(project_workspace.subdir(project_id, "documents")) / "code"


def _read_saved_source(code_root, filename):
    valid, _reason = validate_code_filename(filename)
    if not valid:
        return None
    root = Path(os.path.realpath(code_root))
    artifact = Path(os.path.realpath(root / filename))
    if artifact.parent != root or not artifact.is_file():
        return None
    try:
        data = artifact.read_bytes()
    except OSError:
        return None
    if not data or len(data) > MAX_CODE_FILE_BYTES:
        return None
    return data


def _job_dir(job_id):
    if not isinstance(job_id, str) or _JOB_ID.fullmatch(job_id) is None:
        return None
    candidate = Path(os.path.realpath(JOBS_ROOT / job_id))
    root = Path(os.path.realpath(JOBS_ROOT))
    if candidate.parent != root:
        return None
    return candidate


def _trusted(proxy_secret, headers, payload, path, remote_addr, nonce_ledger, now):
    verified = verify_proxy_request(
        proxy_secret, headers, payload, path=path,
        remote_addr=remote_addr, now=now, nonce_ledger=nonce_ledger,
    )
    if verified.get("trusted") is not True:
        return None, verified.get("reason") or "proxy_untrusted"
    return verified, None


def _render_wsb(job_dir, python_home, toolchain_site):
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    from xml.sax.saxutils import escape

    rendered = (
        template
        .replace("__INPUT__", escape(str(job_dir / "input")))
        .replace("__OUTPUT__", escape(str(job_dir / "output")))
        .replace("__PYTHON__", escape(str(python_home)))
        .replace("__SITE__", escape(str(toolchain_site)))
    )
    return rendered


def prepare_package(
    *, proxy_secret, headers, payload, path, remote_addr, nonce_ledger, now=None
):
    """Stage a packaging job after an explicit, separate packaging consent."""
    if not packager_enabled():
        return _result(False, "packaging_disabled", packaging_enabled=False)

    if not isinstance(payload, dict) or set(payload) != _PREPARE_FIELDS:
        return _result(False, "packaging_payload_invalid")

    # The browser must state packaging consent explicitly. It is never inferred
    # from a previous save or run approval.
    if payload.get("confirm_package") is not True:
        return _result(False, "explicit_package_confirmation_required")

    verified, reason = _trusted(
        proxy_secret, headers, payload, path, remote_addr, nonce_ledger, now)
    if verified is None:
        return _result(False, reason)

    project_id = payload.get("project_id")
    filename = payload.get("filename")
    if not validate_project_id(project_id):
        return _result(False, "packaging_payload_invalid")

    try:
        code_root = _project_code_root(project_id)
    except Exception:
        return _result(False, "packaging_project_unavailable")

    source = _read_saved_source(code_root, filename)
    if source is None:
        return _result(False, "saved_python_artifact_unavailable")

    if not PYTHON_HOME.is_dir() or not (PYTHON_HOME / "python.exe").is_file():
        return _result(False, "packaging_python_home_unavailable")
    if not TOOLCHAIN_SITE.is_dir():
        return _result(False, "packaging_toolchain_unavailable")
    if not TEMPLATE_PATH.is_file() or not BUILD_SCRIPT_PATH.is_file():
        return _result(False, "packaging_assets_unavailable")

    digest = _sha256_bytes(source)
    exe_name = exe_name_for(filename)
    job_id = secrets.token_hex(8)
    job_dir = JOBS_ROOT / job_id

    try:
        (job_dir / "input").mkdir(parents=True, exist_ok=False)
        (job_dir / "output").mkdir(parents=True, exist_ok=False)
        (job_dir / "input" / "source.py").write_bytes(source)
        shutil.copy2(BUILD_SCRIPT_PATH, job_dir / "input" / "build_sandbox.ps1")
        (job_dir / "input" / "job.json").write_text(
            json.dumps({
                "contract": SANDBOX_BUILD_CONTRACT,
                "job_id": job_id,
                "project_id": project_id,
                "filename": filename,
                "exe_name": exe_name,
                "source_sha256": digest,
                "created_at": time.time(),
            }, indent=2),
            encoding="utf-8",
        )
        wsb = _render_wsb(job_dir, PYTHON_HOME, TOOLCHAIN_SITE)
        (job_dir / "package.wsb").write_text(wsb, encoding="utf-8")
    except OSError as exc:
        return _result(False, "packaging_staging_failed", detail=str(exc)[:200])

    # Re-read what was actually written: the digest the sandbox will verify must
    # be the digest of the staged bytes, not of the bytes we intended to write.
    staged_digest = _sha256_file(job_dir / "input" / "source.py")
    if not hmac.compare_digest(staged_digest, digest):
        return _result(False, "packaging_staged_digest_mismatch")

    return _result(
        True,
        None,
        stage="awaiting_sandbox",
        job_id=job_id,
        project_id=project_id,
        filename=filename,
        exe_name=exe_name,
        source_sha256=digest,
        wsb_path=str(job_dir / "package.wsb"),
        output_dir=str(job_dir / "output"),
        manual_launch_required=True,
        launch_instruction=(
            "Open the .wsb file to start the isolated build. Networking is "
            "disabled; only the source, the Python runtime and PyInstaller are "
            "mounted read-only, and only the output folder is writable."
        ),
        sandbox_network="disabled",
        host_build_available=False,
    )


def _read_manifest(job_dir):
    path = job_dir / "output" / "manifest.json"
    if not path.is_file():
        return None
    try:
        # The sandbox writes this with Windows PowerShell 5.1
        # `Set-Content -Encoding utf8`, which emits a UTF-8 BOM. `utf-8-sig`
        # strips it when present and behaves identically when absent, so a
        # BOM must not turn a valid manifest into an unreadable one.
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {"status": "unreadable"}


def package_status(
    *, proxy_secret, headers, payload, path, remote_addr, nonce_ledger, now=None
):
    """Read the sandbox result, verify it, and deliver the EXE."""
    if not packager_enabled():
        return _result(False, "packaging_disabled", packaging_enabled=False)

    if not isinstance(payload, dict) or set(payload) != _STATUS_FIELDS:
        return _result(False, "packaging_payload_invalid")

    verified, reason = _trusted(
        proxy_secret, headers, payload, path, remote_addr, nonce_ledger, now)
    if verified is None:
        return _result(False, reason)

    project_id = payload.get("project_id")
    if not validate_project_id(project_id):
        return _result(False, "packaging_payload_invalid")

    job_dir = _job_dir(payload.get("job_id"))
    if job_dir is None or not job_dir.is_dir():
        return _result(False, "packaging_job_unavailable")

    job_file = job_dir / "input" / "job.json"
    try:
        job = json.loads(job_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _result(False, "packaging_job_unavailable")

    # A job belongs to exactly one project.
    if job.get("project_id") != project_id:
        return _result(False, "packaging_job_project_mismatch")

    manifest = _read_manifest(job_dir)
    if manifest is None:
        return _result(
            True, None,
            stage="awaiting_sandbox",
            job_id=job["job_id"],
            wsb_path=str(job_dir / "package.wsb"),
            manual_launch_required=True,
            sandbox_network="disabled",
            host_build_available=False,
        )

    if manifest.get("contract") != SANDBOX_BUILD_CONTRACT:
        return _result(False, "packaging_manifest_contract_invalid")
    if manifest.get("job_id") != job.get("job_id"):
        return _result(False, "packaging_manifest_job_mismatch")
    if manifest.get("source_sha256") != job.get("source_sha256"):
        return _result(False, "packaging_manifest_source_mismatch")
    if manifest.get("status") != "ok":
        return _result(
            False,
            "packaging_build_%s" % (manifest.get("status") or "failed"),
            exit_code=manifest.get("exit_code"),
            log_path=str(job_dir / "output" / "build.log"),
        )

    exe_name = job.get("exe_name")
    if not isinstance(exe_name, str) or _SAFE_NAME.sub("_", exe_name) != exe_name:
        return _result(False, "packaging_manifest_exe_name_invalid")

    exe_path = job_dir / "output" / "dist" / (exe_name + ".exe")
    if not exe_path.is_file():
        return _result(False, "packaging_exe_missing")

    actual = _sha256_file(exe_path)
    declared = str(manifest.get("exe_sha256") or "")
    if _SHA256.fullmatch(declared) is None or not hmac.compare_digest(actual, declared):
        return _result(False, "packaging_exe_digest_mismatch")
    if int(manifest.get("exe_size") or 0) != exe_path.stat().st_size:
        return _result(False, "packaging_exe_size_mismatch")

    # Deliver into the project's own code folder, then expose it through the
    # existing artifact resolver.
    try:
        code_root = _project_code_root(project_id)
        dist_dir = code_root / "dist"
        dist_dir.mkdir(parents=True, exist_ok=True)
        target = dist_dir / (exe_name + ".exe")
        shutil.copy2(exe_path, target)
        delivered = _sha256_file(target)
    except OSError as exc:
        return _result(False, "packaging_delivery_failed", detail=str(exc)[:200])

    if not hmac.compare_digest(delivered, actual):
        return _result(False, "packaging_delivery_digest_mismatch")

    artifact = (
        "/artifacts/project_media/%s/documents/code/dist/%s.exe?download=1"
        % (project_id, exe_name)
    )

    return _result(
        True,
        None,
        stage="delivered",
        job_id=job["job_id"],
        exe_name=exe_name,
        exe_sha256=actual,
        exe_size=exe_path.stat().st_size,
        source_sha256=job.get("source_sha256"),
        local_path=str(target),
        artifact_url=artifact,
        manifest_path=str(job_dir / "output" / "manifest.json"),
        sandbox_network="disabled",
        host_build_available=False,
    )


def describe_packager():
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "default_enabled": False,
        "opt_in_environment": OPT_IN_ENV,
        "scope": SCOPE,
        "action": ACTION,
        "builder": "windows_sandbox",
        "sandbox_network": "disabled",
        "host_build_available": False,
        "host_executes_generated_code": False,
        "separate_from_save": True,
        "separate_from_run": True,
        "read_only_mounts": ["source", "python_home", "pyinstaller_toolchain"],
        "writable_mounts": ["output"],
        "python_home": str(PYTHON_HOME),
        "toolchain": str(TOOLCHAIN_SITE),
        "manual_launch_required": True,
        "autolaunch_verified": False,
    }
