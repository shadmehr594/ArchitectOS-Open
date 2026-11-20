# -*- coding: utf-8 -*-
"""CODER-06 — SAFE PYTHON SYNTAX VALIDATION V1.

Validate the SYNTAX of one existing ``.py`` file inside the current project's
sandbox ``data/projects/<project_id>/documents/code/``.

Scope: syntax validation ONLY. This module never executes, imports, evaluates
or repairs the target program, and it never writes anything.

Isolation
---------
The check runs in a **bounded subprocess**::

    <python> -I -S -B -c "<fixed checker script>"     (source on stdin)

* the checker script is a FIXED constant — no user/model text is interpolated;
* the source is supplied **via stdin**, never as a path or an argument;
* ``-I`` isolated mode, ``-S`` no site, ``-B`` never write bytecode;
* a hard timeout bounds the run;
* the subprocess only calls ``compile()`` — it does not import or run the file,
  so no ``__pycache__`` / ``.pyc`` is produced and the source is untouched.
"""

import json
import os
import subprocess
import sys

from core.runtime.subprocess_no_window_v1 import no_window_kwargs

from core.chat.project_code_file_writer_v1 import (
    CODE_SUBDIR,
    PARENT_SUBDIR,
    MAX_CODE_FILE_BYTES,
    _canonical,
    _is_direct_child,
    _is_inside,
    _is_reparse_point,
    validate_code_filename,
)

CONTRACT = "ProjectCodeSyntaxCheckerV1"
VERSION = "1.0"

CHECK_TIMEOUT_SECONDS = 20

# The FIXED checker script. It reads the source from stdin and only COMPILES
# it (which cannot execute it). Nothing here is derived from user input.
_CHECKER_SCRIPT = r"""
import sys, json

raw = sys.stdin.buffer.read()

try:
    text = raw.decode("utf-8")
except UnicodeDecodeError as exc:
    print(json.dumps({
        "ok": False, "status": "invalid_encoding",
        "message": str(exc), "line": None, "column": None,
    }))
    raise SystemExit(0)

try:
    compile(text, "<project_code>", "exec")
except SyntaxError as exc:
    print(json.dumps({
        "ok": False, "status": "syntax_error",
        "message": getattr(exc, "msg", str(exc)),
        "line": getattr(exc, "lineno", None),
        "column": getattr(exc, "offset", None),
    }))
    raise SystemExit(0)
except ValueError as exc:
    print(json.dumps({
        "ok": False, "status": "value_error",
        "message": str(exc), "line": None, "column": None,
    }))
    raise SystemExit(0)

print(json.dumps({"ok": True, "status": "valid"}))
"""


def _base_result(project_id, filename):
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "project_id": str(project_id) if project_id else None,
        "filename": filename,
        "relative_path": None,
        "status": "failed",
        "reason": None,
        "syntax_valid": False,
        "python_version": None,
        "message": None,
        "line": None,
        "column": None,
        "bytes_read": 0,
    }


def check_project_code_file(project_id, filename, documents_root=None):
    """Validate the SYNTAX of ``<project>/documents/code/<filename>``."""

    result = _base_result(project_id, filename)

    # 1. verified project context only
    if not isinstance(project_id, str) or not project_id.strip():
        result["reason"] = "missing_project_context"
        return result

    # 2. filename policy (shared with CODER-05)
    ok, reason = validate_code_filename(filename)
    if not ok:
        result["reason"] = reason
        return result

    # 3. resolve the sandbox from the VERIFIED project id
    try:
        if documents_root is None:
            from core.project.project_workspace_v1 import project_workspace

            documents_root = project_workspace.subdir(project_id, PARENT_SUBDIR)
        sandbox = os.path.join(documents_root, CODE_SUBDIR)
    except Exception:
        result["reason"] = "sandbox_unavailable"
        return result

    project_dir = _canonical(os.path.dirname(_canonical(documents_root)))

    if os.path.exists(sandbox) and _is_reparse_point(sandbox):
        result["reason"] = "sandbox_is_link"
        return result

    sandbox = _canonical(sandbox)

    if not _is_inside(sandbox, project_dir):
        result["reason"] = "sandbox_outside_project"
        return result

    target = _canonical(os.path.join(sandbox, filename))

    if not _is_direct_child(sandbox, target):
        result["reason"] = "path_escape"
        return result

    if not os.path.isfile(target):
        result["reason"] = "missing_file"
        return result

    if _is_reparse_point(target):
        result["reason"] = "target_is_link"
        return result

    result["relative_path"] = "%s/%s/%s" % (PARENT_SUBDIR, CODE_SUBDIR, filename)

    # 4. size limit + safe UTF-8 read
    try:
        size = os.path.getsize(target)
        if size > MAX_CODE_FILE_BYTES:
            result["reason"] = "file_too_large"
            return result
        with open(target, "rb") as handle:
            raw = handle.read(MAX_CODE_FILE_BYTES + 1)
    except Exception:
        result["reason"] = "read_failed"
        return result

    if len(raw) > MAX_CODE_FILE_BYTES:
        result["reason"] = "file_too_large"
        return result

    result["bytes_read"] = len(raw)

    # 5. bounded, isolated checker subprocess (source via stdin)
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", _CHECKER_SCRIPT],
            input=raw,
            capture_output=True,
            timeout=CHECK_TIMEOUT_SECONDS,
            cwd=sandbox,
            # NO_CONSOLE_WINDOW — the checker must never flash a console.
            **no_window_kwargs(),
        )
    except subprocess.TimeoutExpired:
        result["reason"] = "checker_timeout"
        return result
    except Exception:
        result["reason"] = "checker_unavailable"
        return result

    stdout = (completed.stdout or b"").decode("utf-8", errors="replace").strip()

    if completed.returncode != 0 or not stdout:
        result["reason"] = "checker_failed"
        return result

    try:
        payload = json.loads(stdout.splitlines()[-1])
    except Exception:
        result["reason"] = "checker_output_invalid"
        return result

    result["python_version"] = "%d.%d.%d" % sys.version_info[:3]

    if payload.get("ok"):
        result["status"] = "valid"
        result["syntax_valid"] = True
        result["reason"] = None
        result["message"] = "syntax is valid"
        return result

    result["status"] = "invalid"
    result["syntax_valid"] = False
    result["reason"] = payload.get("status") or "syntax_error"
    result["message"] = payload.get("message")
    result["line"] = payload.get("line")
    result["column"] = payload.get("column")
    return result
