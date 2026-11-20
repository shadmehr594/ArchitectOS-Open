# -*- coding: utf-8 -*-
"""CODER-06 — SAFE PYTHON SYNTAX VALIDATION (focused tests).

All work happens in DISPOSABLE temp sandboxes. The user's real project files
are never touched and no generated Python is executed or imported.
"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.chat.project_code_syntax_checker_v1 import (  # noqa: E402
    check_project_code_file,
)
from core.chat.project_code_file_writer_v1 import (  # noqa: E402
    create_project_code_file,
)
from core.intent_router import intent_router  # noqa: E402


VALID = (
    "import tkinter as tk\n\n"
    "def main():\n"
    "    root = tk.Tk()\n"
    "    root.mainloop()\n\n"
    "if __name__ == '__main__':\n"
    "    main()\n"
)


def _sandbox(source=VALID, name="calculator.py"):
    docs = tempfile.mkdtemp(prefix="coder06_docs_")
    code = os.path.join(docs, "code")
    os.makedirs(code, exist_ok=True)
    if source is not None:
        with open(os.path.join(code, name), "wb") as fh:
            fh.write(source.encode("utf-8"))
    return docs, code


# ----------------------------------------------------------------------
# 1. Valid source
# ----------------------------------------------------------------------

def test_valid_file():
    docs, code = _sandbox()
    try:
        res = check_project_code_file("p1", "calculator.py", documents_root=docs)
        assert res["status"] == "valid", res
        assert res["syntax_valid"] is True
        assert res["python_version"], res
        assert res["relative_path"] == "documents/code/calculator.py"
        assert res["bytes_read"] == len(VALID.encode("utf-8"))
    finally:
        shutil.rmtree(docs, ignore_errors=True)


# ----------------------------------------------------------------------
# 2. Invalid sources + error position
# ----------------------------------------------------------------------

def test_invalid_sources_report_line_and_column():
    cases = [
        ("def f()\n    return 1\n", "syntax_error"),          # missing colon
        ("def f():\nreturn 1\n", "syntax_error"),             # bad indentation
        ("x = (1 + 2\n", "syntax_error"),                     # unclosed paren
        ("def f(:\n    pass\n", "syntax_error"),              # invalid syntax
    ]
    for source, expected in cases:
        docs, _ = _sandbox(source)
        try:
            res = check_project_code_file("p2", "calculator.py", documents_root=docs)
            assert res["status"] == "invalid", (source, res)
            assert res["syntax_valid"] is False
            assert res["reason"] == expected, (source, res["reason"])
            assert res["message"], (source, res)
            assert isinstance(res["line"], int) and res["line"] >= 1, (source, res)
            assert isinstance(res["column"], int) and res["column"] >= 1, (source, res)
        finally:
            shutil.rmtree(docs, ignore_errors=True)


def test_line_number_is_accurate():
    # the error is on line 3
    source = "a = 1\nb = 2\ndef f()\n    pass\n"
    docs, _ = _sandbox(source)
    try:
        res = check_project_code_file("p3", "calculator.py", documents_root=docs)
        assert res["status"] == "invalid", res
        assert res["line"] == 3, res
    finally:
        shutil.rmtree(docs, ignore_errors=True)


# ----------------------------------------------------------------------
# 3. Missing file / bad filename / bad context / traversal / oversize
# ----------------------------------------------------------------------

def test_missing_file():
    docs, _ = _sandbox(source=None)
    try:
        res = check_project_code_file("p4", "calculator.py", documents_root=docs)
        assert res["reason"] == "missing_file", res
    finally:
        shutil.rmtree(docs, ignore_errors=True)


def test_bad_filenames_rejected():
    docs, _ = _sandbox()
    try:
        for name in ("../evil.py", "sub/evil.py", "C:evil.py", "con.py", "evil.txt"):
            res = check_project_code_file("p5", name, documents_root=docs)
            assert res["status"] == "failed", (name, res)
            assert res["reason"] not in (None, "missing_file"), (name, res)
    finally:
        shutil.rmtree(docs, ignore_errors=True)


def test_missing_project_context():
    res = check_project_code_file(None, "calculator.py")
    assert res["reason"] == "missing_project_context", res
    res = check_project_code_file("", "calculator.py")
    assert res["reason"] == "missing_project_context", res


def test_oversized_source():
    docs, _ = _sandbox("# " + "x" * (300 * 1024) + "\n")
    try:
        res = check_project_code_file("p6", "calculator.py", documents_root=docs)
        assert res["reason"] == "file_too_large", res
    finally:
        shutil.rmtree(docs, ignore_errors=True)


# ----------------------------------------------------------------------
# 4. Source untouched; no artifacts; never executed
# ----------------------------------------------------------------------

def test_source_bytes_unchanged_and_no_artifacts():
    docs, code = _sandbox()
    target = os.path.join(code, "calculator.py")
    try:
        before = open(target, "rb").read()
        check_project_code_file("p7", "calculator.py", documents_root=docs)
        after = open(target, "rb").read()
        assert before == after, "source changed!"

        artifacts = []
        for root, dirs, files in os.walk(docs):
            for f in files:
                if f.endswith(".pyc") or f.endswith(".pyo"):
                    artifacts.append(os.path.join(root, f))
            for d in dirs:
                if d == "__pycache__":
                    artifacts.append(os.path.join(root, d))
        assert artifacts == [], artifacts
    finally:
        shutil.rmtree(docs, ignore_errors=True)


def test_source_is_never_executed():
    # if this were executed it would create MARKER.txt next to the source
    source = "open('MARKER.txt', 'w').write('boom')\n"
    docs, code = _sandbox(source)
    try:
        res = check_project_code_file("p8", "calculator.py", documents_root=docs)
        assert res["status"] == "valid", res          # syntactically valid
        assert not os.path.exists(os.path.join(code, "MARKER.txt")), "SOURCE WAS EXECUTED"
    finally:
        shutil.rmtree(docs, ignore_errors=True)


# ----------------------------------------------------------------------
# 5. Routing
# ----------------------------------------------------------------------

def _route(text):
    return intent_router.route(text, None, {})


def test_syntax_check_request_routes_to_boundary():
    route = _route("فایل calculator.py را از نظر خطاهای نحوی بررسی کن.")
    assert route.get("intent") == "code" and route.get("mode") == "capability", route


def test_execution_request_stays_blocked():
    route = _route("فایل calculator.py را اجرا کن و نتیجه را گزارش بده.")
    assert route.get("intent") == "code" and route.get("mode") == "capability", route


def test_coding_chat_uses_coder_model():
    route = _route("یک ماشین‌حساب با پایتون بنویس و کد کامل را بنویس.")
    assert route.get("intent") == "chat" and route.get("model_role") == "coder", route


def test_coder05_creation_still_works():
    docs = tempfile.mkdtemp(prefix="coder06_create_")
    try:
        res = create_project_code_file("p9", "calculator.py", VALID, documents_root=docs)
        assert res["status"] == "created" and res["verified_on_disk"], res
        chk = check_project_code_file("p9", "calculator.py", documents_root=docs)
        assert chk["syntax_valid"] is True, chk
    finally:
        shutil.rmtree(docs, ignore_errors=True)


def test_architecture_unaffected():
    for text, expected in [
        ("یک ساختمان بساز", "design_request"),
        ("پلان ساختمان ایجاد کن", "design_request"),
        ("یک ویلا طراحی کن", "villa_design"),
    ]:
        route = _route(text)
        assert route.get("intent") == "design", (text, route)
        assert route.get("design_type") == expected, (text, route)


def test_checker_has_no_execution_surface():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "core", "chat", "project_code_syntax_checker_v1.py",
    )
    src = open(path, encoding="utf-8").read()
    for forbidden in ("runpy", "eval(", "exec(", "os.system", "importlib"):
        assert forbidden not in src, forbidden
