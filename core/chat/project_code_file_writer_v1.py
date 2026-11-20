# -*- coding: utf-8 -*-
"""CODER-05 — SAFE PROJECT CODE FILE CREATION V1.

ONE narrow capability: write a single ``.py`` source file inside the CURRENT
project's isolated sandbox ``data/projects/<project_id>/documents/code/``.

Security model
--------------
* The project id comes from the VERIFIED session — never from the model or the
  user text.
* The filename must be a bare Python filename (``[A-Za-z_][A-Za-z0-9_]*.py``):
  no separators, no drive prefix, no traversal, no reserved Windows device
  names, no leading dot.
* Containment is proven with CANONICAL paths (``os.path.realpath``) compared
  COMPONENT-WISE — never a string ``startswith``.
* Symlinks / junctions / reparse points are refused: the sandbox directory and
  the target file must not be links, and the sandbox must stay inside the
  project directory.
* Size is capped; the write is ATOMIC (temp file in the same directory +
  ``os.replace``); an existing file is never overwritten without an explicit
  overwrite request; the bytes are read back and compared before success.

No execution, no import, no shell access. This module only writes text.
"""

import os
import re
import time

CONTRACT = "ProjectCodeFileWriterV1"
VERSION = "1.0"

CODE_SUBDIR = "code"
PARENT_SUBDIR = "documents"

MAX_CODE_FILE_BYTES = 256 * 1024

# A bare, safe Python filename.
_SAFE_PY_FILENAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}\.py$")

# Project/session identifiers enter the chat API from headers or request data.
# The writer must not let one of those values become a path component until it
# has been validated independently of ProjectWorkspace. Real ArchitectOS ids
# (`project_<hex>`) and the existing bounded test ids are covered by this
# conservative portable subset.
_SAFE_PROJECT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")

# Windows reserved device names (reserved even with an extension).
_RESERVED_NAMES = frozenset(
    ["con", "prn", "aux", "nul"]
    + ["com%d" % i for i in range(1, 10)]
    + ["lpt%d" % i for i in range(1, 10)]
)

_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def _is_reparse_point(path):
    """True for a symlink / junction / other reparse point."""
    try:
        if os.path.islink(path):
            return True
        st = os.lstat(path)
        attrs = getattr(st, "st_file_attributes", 0)
        return bool(attrs & _FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return False


def _canonical(path):
    return os.path.realpath(os.path.abspath(path))


def _parts(path):
    return os.path.normcase(os.path.normpath(path)).split(os.sep)


def _is_inside(child, parent):
    c, p = _parts(child), _parts(parent)
    return len(c) > len(p) and c[: len(p)] == p


def _is_direct_child(parent, child):
    c, p = _parts(child), _parts(parent)
    return len(c) == len(p) + 1 and c[: len(p)] == p


def validate_code_filename(filename):
    """Return (ok, reason). Reason is None when ok."""
    if not isinstance(filename, str) or not filename:
        return False, "missing_filename"
    if filename != filename.strip():
        return False, "surrounding_whitespace"
    if "/" in filename or "\\" in filename:
        return False, "path_separator"
    if ".." in filename or filename in (".",):
        return False, "traversal"
    if os.path.isabs(filename) or re.match(r"^[A-Za-z]:", filename):
        return False, "absolute_or_drive"
    if not _SAFE_PY_FILENAME.match(filename):
        return False, "unsafe_filename"
    if filename.split(".", 1)[0].lower() in _RESERVED_NAMES:
        return False, "reserved_device_name"
    return True, None


def validate_project_id(project_id):
    """Return True only for one portable, non-device path component."""
    if not isinstance(project_id, str) or not project_id.strip():
        return False
    if project_id != project_id.strip():
        return False
    if not _SAFE_PROJECT_ID.fullmatch(project_id):
        return False
    if project_id.lower() in _RESERVED_NAMES:
        return False
    return True


def extract_python_code(text):
    """The LAST complete ```python fenced block, or None."""
    if not isinstance(text, str) or "```" not in text:
        return None
    blocks = re.findall(
        r"```[ \t]*(?:python|py)?[ \t]*\r?\n(.*?)```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    blocks = [b for b in blocks if b and b.strip()]
    if not blocks:
        return None
    return blocks[-1].strip("\n")


def create_project_code_file(
    project_id,
    filename,
    content,
    overwrite=False,
    documents_root=None,
):
    """Write ``content`` to ``<project>/documents/code/<filename>``.

    Returns a machine-readable result dict. ``status`` is ``created`` /
    ``overwritten`` / ``failed``; ``verified_on_disk`` is True only after the
    bytes were read back and matched.
    """

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "project_id": str(project_id) if project_id else None,
        "filename": filename,
        "status": "failed",
        "reason": None,
        "relative_path": None,
        "bytes_written": 0,
        "created": False,
        "overwritten": False,
        "verified_on_disk": False,
    }

    # 1. verified project context only
    if not isinstance(project_id, str) or not project_id.strip():
        result["reason"] = "missing_project_context"
        return result

    if not validate_project_id(project_id):
        result["reason"] = "invalid_project_id"
        return result

    # 2. filename policy
    ok, reason = validate_code_filename(filename)
    if not ok:
        result["reason"] = reason
        return result

    # 3. content policy
    if not isinstance(content, str) or not content.strip():
        result["reason"] = "empty_source"
        return result
    data = content.encode("utf-8")
    if len(data) > MAX_CODE_FILE_BYTES:
        result["reason"] = "file_too_large"
        return result

    # 4. resolve the sandbox from the VERIFIED project id
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

    try:
        os.makedirs(sandbox, exist_ok=True)
    except Exception:
        result["reason"] = "sandbox_unavailable"
        return result

    # Re-check AFTER creation. The pre-check above only runs when the sandbox
    # already existed, so a link that appears between the two points (or a host
    # that cannot report the link before it is materialised) would otherwise
    # skip the guard entirely.
    if _is_reparse_point(sandbox):
        result["reason"] = "sandbox_is_link"
        return result

    sandbox = _canonical(sandbox)

    # component-wise containment (never startswith)
    if not _is_inside(sandbox, project_dir):
        result["reason"] = "sandbox_outside_project"
        return result

    target = _canonical(os.path.join(sandbox, filename))
    if not _is_direct_child(sandbox, target):
        result["reason"] = "path_escape"
        return result

    exists = os.path.exists(target)

    if exists and _is_reparse_point(target):
        result["reason"] = "target_is_link"
        return result

    # 5. overwrite policy
    if exists and not overwrite:
        result["reason"] = "already_exists"
        return result

    # 6. atomic write
    tmp = os.path.join(
        sandbox, ".%s.tmp-%d" % (filename, int(time.time() * 1000))
    )
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        result["reason"] = "write_failed"
        return result

    # 7. verify from disk
    try:
        with open(target, "rb") as handle:
            on_disk = handle.read()
        verified = on_disk == data
    except Exception:
        verified = False

    if not verified:
        result["reason"] = "verification_failed"
        return result

    result.update(
        {
            "status": "overwritten" if exists else "created",
            "reason": None,
            "relative_path": "%s/%s/%s" % (PARENT_SUBDIR, CODE_SUBDIR, filename),
            "bytes_written": len(data),
            "created": not exists,
            "overwritten": exists,
            "verified_on_disk": True,
        }
    )
    return result
