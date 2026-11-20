# -*- coding: utf-8 -*-
"""CODER-05 — SAFE PROJECT CODE FILE CREATION (focused tests).

Every write happens in a DISPOSABLE temp directory; no existing project is
touched. No generated Python is imported or executed.
"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.chat.project_code_file_writer_v1 import (  # noqa: E402
    create_project_code_file,
    validate_code_filename,
    extract_python_code,
    _is_reparse_point,
)
from core.intent_router import intent_router  # noqa: E402


SOURCE = (
    "import tkinter as tk\n\n"
    "def main():\n"
    "    root = tk.Tk()\n"
    "    root.mainloop()\n\n"
    "if __name__ == '__main__':\n"
    "    main()\n"
)


def _tmp_docs():
    return tempfile.mkdtemp(prefix="coder05_docs_")


# ----------------------------------------------------------------------
# 1. Successful creation + content fidelity
# ----------------------------------------------------------------------

def test_create_and_verify():
    docs = _tmp_docs()
    try:
        res = create_project_code_file(
            "project_test01", "calculator.py", SOURCE, documents_root=docs
        )
        assert res["status"] == "created", res
        assert res["verified_on_disk"] is True
        assert res["relative_path"] == "documents/code/calculator.py"
        assert res["bytes_written"] == len(SOURCE.encode("utf-8"))

        target = os.path.join(docs, "code", "calculator.py")
        assert os.path.isfile(target)
        with open(target, "rb") as fh:
            assert fh.read().decode("utf-8") == SOURCE
    finally:
        shutil.rmtree(docs, ignore_errors=True)


def test_duplicate_then_overwrite():
    docs = _tmp_docs()
    try:
        assert create_project_code_file(
            "project_test02", "a.py", SOURCE, documents_root=docs
        )["status"] == "created"

        dup = create_project_code_file(
            "project_test02", "a.py", SOURCE + "\n# changed\n", documents_root=docs
        )
        assert dup["status"] == "failed" and dup["reason"] == "already_exists", dup

        over = create_project_code_file(
            "project_test02", "a.py", "# v2\n", overwrite=True, documents_root=docs
        )
        assert over["status"] == "overwritten", over
        with open(os.path.join(docs, "code", "a.py"), "rb") as fh:
            assert fh.read().decode("utf-8") == "# v2\n"
    finally:
        shutil.rmtree(docs, ignore_errors=True)


# ----------------------------------------------------------------------
# 2. Filename / path security
# ----------------------------------------------------------------------

def test_missing_project_context():
    res = create_project_code_file(None, "a.py", SOURCE)
    assert res["status"] == "failed" and res["reason"] == "missing_project_context"


def test_rejects_unsafe_filenames():
    # every one of these MUST be rejected (the reason is informative)
    bad = [
        "../evil.py",
        "..\\evil.py",
        "sub/evil.py",
        "sub\\evil.py",
        "/etc/evil.py",
        "C:\\evil.py",
        "C:evil.py",
        "con.py",
        "NUL.py",
        "com1.py",
        "evil.txt",
        "calculator.py ",
        "calc-1.py",
        "..py",
        ".hidden.py",
        "",
    ]
    for name in bad:
        ok, why = validate_code_filename(name)
        assert ok is False, (name, why)

    # the unambiguous reasons are exact
    assert validate_code_filename("C:evil.py")[1] == "absolute_or_drive"
    assert validate_code_filename("con.py")[1] == "reserved_device_name"
    assert validate_code_filename("evil.txt")[1] == "unsafe_filename"
    assert validate_code_filename("sub/evil.py")[1] == "path_separator"

    ok, why = validate_code_filename("calculator.py")
    assert ok is True and why is None


def test_rejects_content_and_size():
    docs = _tmp_docs()
    try:
        assert create_project_code_file(
            "p", "a.py", "", documents_root=docs
        )["reason"] == "empty_source"
        assert create_project_code_file(
            "p", "a.py", None, documents_root=docs
        )["reason"] == "empty_source"
        assert create_project_code_file(
            "p", "a.py", "x" * (300 * 1024), documents_root=docs
        )["reason"] == "file_too_large"
    finally:
        shutil.rmtree(docs, ignore_errors=True)


def test_symlinked_sandbox_is_refused():
    import core.chat.project_code_file_writer_v1 as writer

    docs = _tmp_docs()
    outside = tempfile.mkdtemp(prefix="coder05_outside_")
    real_link = False
    try:
        try:
            os.symlink(outside, os.path.join(docs, "code"), target_is_directory=True)
            real_link = _is_reparse_point(os.path.join(docs, "code"))
        except (OSError, NotImplementedError):
            real_link = False

        if not real_link:
            # This host cannot create a detectable link — prove the GUARD
            # fires by simulating a reparse point.
            original = writer._is_reparse_point
            writer._is_reparse_point = lambda p: True
            try:
                res = create_project_code_file(
                    "p", "a.py", SOURCE, documents_root=docs
                )
            finally:
                writer._is_reparse_point = original
        else:
            res = create_project_code_file(
                "p", "a.py", SOURCE, documents_root=docs
            )

        assert res["status"] == "failed" and res["reason"] == "sandbox_is_link", res
        assert not os.path.exists(os.path.join(outside, "a.py"))
    finally:
        shutil.rmtree(docs, ignore_errors=True)
        shutil.rmtree(outside, ignore_errors=True)


# ----------------------------------------------------------------------
# 3. Source extraction (never invent code)
# ----------------------------------------------------------------------

def test_extract_python_code():
    text = "توضیح\n\n```python\nx = 1\n```\n\nو بلوک دوم:\n\n```py\ny = 2\n```"
    assert extract_python_code(text) == "y = 2"
    assert extract_python_code("no code here") is None
    assert extract_python_code("```python\nprint('unclosed')") is None


# ----------------------------------------------------------------------
# 4. Routing: chat vs file vs execution vs architecture
# ----------------------------------------------------------------------

def _route(text):
    return intent_router.route(text, None, {})


def test_ordinary_coding_chat_stays_chat():
    route = _route("یک ماشین‌حساب با پایتون بنویس و کد کامل را بنویس.")
    assert route.get("intent") == "chat"
    assert route.get("model_role") == "coder"


def test_explicit_file_creation_routes_to_capability_boundary():
    route = _route("یک فایل واقعی calculator.py در پروژه بساز.")
    assert route.get("intent") == "code" and route.get("mode") == "capability"


def test_execution_only_request_is_not_a_creation():
    from core.chat.chat_architect import ChatArchitect

    text = "فایل calculator.py را اجرا کن و نتیجه را گزارش بده."
    route = _route(text)
    assert route.get("intent") == "code" and route.get("mode") == "capability"
    # no CREATE action -> the boundary must NOT create anything
    assert not any(a in text for a in ChatArchitect._CODE_CREATE_ACTIONS)


def test_architecture_unaffected():
    for text, expected in [
        ("یک ساختمان بساز", "design_request"),
        ("پلان ساختمان ایجاد کن", "design_request"),
        ("یک ویلا طراحی کن", "villa_design"),
    ]:
        route = _route(text)
        assert route.get("intent") == "design", (text, route)
        assert route.get("design_type") == expected, (text, route)


# ----------------------------------------------------------------------
# 5. No execution surface
# ----------------------------------------------------------------------

def test_writer_has_no_execution_surface():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "core", "chat", "project_code_file_writer_v1.py",
    )
    src = open(path, encoding="utf-8").read()
    for forbidden in ("subprocess", "os.system", "eval(", "exec(", "popen", "shell=True"):
        assert forbidden not in src, forbidden
