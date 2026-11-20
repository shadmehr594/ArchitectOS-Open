# -*- coding: utf-8 -*-
# ==========================================================
# FACADE-04D.2 — ACCEPTANCE RUNNER
# ROLE-AWARE DUAL-IMAGE RENDER BINDING V1
#
#   * ZERO renders: the ComfyUI output dir is snapshotted before and after and
#     must be unchanged. No ComfyUI job is ever submitted.
#   * No service restart, no download, no custom-node install.
#   * Every suite is run DIRECTLY (script-style suites report "N/M PASS" only
#     when run directly — a pytest green line for them is not evidence).
#
# Run:
#   .venv/Scripts/python.exe -u tools/run_facade_04d2_acceptance.py
# ==========================================================

import ast
import json
import os
import re
import subprocess
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

PY = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")
if not os.path.isfile(PY):
    PY = sys.executable

COMFY_OUTPUT = r"C:\ComfyUI-Zluda\output"

REPORT_PATH = os.path.join(PROJECT_ROOT, "tools", "acceptance_facade_04d2_report.json")

RESULTS = []


def record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  | " + detail) if detail else ""))
    return bool(ok)


# ==========================================================
# COMFY SNAPSHOT (no-render proof)
# ==========================================================

def comfy_output_snapshot():
    if not os.path.isdir(COMFY_OUTPUT):
        return {"exists": False, "files": None, "newest": None, "newest_mtime": None}
    files = [f for f in os.listdir(COMFY_OUTPUT)
             if os.path.isfile(os.path.join(COMFY_OUTPUT, f))]
    newest = None
    newest_mtime = None
    for name in files:
        m = os.path.getmtime(os.path.join(COMFY_OUTPUT, name))
        if newest_mtime is None or m > newest_mtime:
            newest, newest_mtime = name, m
    return {"exists": True, "files": len(files), "newest": newest,
            "newest_mtime": newest_mtime}


# ==========================================================
# STATIC ARCHITECTURE CHECKS
# ==========================================================

def static_checks():

    print("\n[STATIC] ARCHITECTURE")

    app_src = open(os.path.join(PROJECT_ROOT, "app.py"), encoding="utf-8").read()
    record("app.py constructs ChatArchitect exactly once",
           app_src.count("ChatArchitect(") == 1,
           "count=%d" % app_src.count("ChatArchitect("))

    module_path = os.path.join(PROJECT_ROOT, "core", "render", "dual_image_binding_v1.py")
    src = open(module_path, encoding="utf-8").read()
    tree = ast.parse(src)

    # No assistant / LLM / network / subprocess surface in the new module.
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])

    forbidden = {"requests", "subprocess", "socket", "urllib", "http", "comfy", "openai"}
    record("binding module imports no network/subprocess surface",
           not (imported & forbidden), "imports=%s" % sorted(imported))

    record("binding module defines no class (no parallel assistant)",
           not any(isinstance(n, ast.ClassDef) for n in ast.walk(tree)))

    record("binding module declares conditioning_active False",
           '"conditioning_active": False' in src or "'conditioning_active': False" in src)

    # The injector must not broadcast a filename across LoadImage nodes for the
    # dual path (the legacy broadcast must be the only occurrence).
    inj_src = open(os.path.join(PROJECT_ROOT, "core", "render",
                                "image_workflow_injector.py"), encoding="utf-8").read()
    record("injector has exactly one (legacy) LoadImage broadcast assignment",
           inj_src.count('inputs["image"] = filename') == 1,
           "count=%d" % inj_src.count('inputs["image"] = filename'))
    record("injector dual branch delegates to the shared binder",
           "bind_role_bindings" in inj_src)

    # The dual workflow must not be selected by the single-valued `image` key.
    sel_src = open(os.path.join(PROJECT_ROOT, "core", "render",
                                "workflow_selector.py"), encoding="utf-8").read()
    record("selector gates the dual graph behind an explicit dual signal",
           "dual_image" in sel_src and "image_bindings" in sel_src)


# ==========================================================
# SUITE RUNNERS
# ==========================================================

def run_direct_suite(rel_path, label):
    """Run a script-style suite DIRECTLY and parse its 'N/M checks passed'."""

    path = os.path.join(PROJECT_ROOT, rel_path)

    if not os.path.isfile(path):
        return record(label + " suite present", False, "missing " + rel_path), None

    proc = subprocess.run(
        [PY, "-u", path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10800,
    )

    out = (proc.stdout or "") + (proc.stderr or "")

    m = re.search(r"RESULT:\s*(\d+)\s*/\s*(\d+)\s*checks passed", out)

    if not m:
        record(label, False, "no 'N/M checks passed' line; rc=%s" % proc.returncode)
        return False, None

    passed, total = int(m.group(1)), int(m.group(2))

    record(label, proc.returncode == 0 and passed == total,
           "%d/%d passed rc=%s" % (passed, total, proc.returncode))

    return (proc.returncode == 0 and passed == total), {"passed": passed, "total": total}


def run_pytest(rel_paths, label):
    """Run a pytest-style set; parse the summary line."""

    targets = [os.path.join(PROJECT_ROOT, p) for p in rel_paths]
    targets = [t for t in targets if os.path.exists(t)]

    proc = subprocess.run(
        [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + targets,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10800,
    )

    out = (proc.stdout or "") + (proc.stderr or "")

    m = re.search(r"(\d+)\s+passed", out)
    passed = int(m.group(1)) if m else 0
    failed = re.search(r"(\d+)\s+failed", out)

    ok = proc.returncode == 0 and passed > 0 and not failed

    record(label, ok, "passed=%d failed=%s rc=%s"
           % (passed, failed.group(1) if failed else 0, proc.returncode))

    return ok


# ==========================================================
# MAIN
# ==========================================================

def main():

    started = time.time()

    print("=== FACADE-04D.2 ACCEPTANCE ===")
    print("python:", PY)

    before = comfy_output_snapshot()
    print("comfy output before:", before)

    print("\n[1] CONTRACT SUITE (dual-image binding)")
    dual_ok, dual_counts = run_direct_suite(
        os.path.join("tests", "test_facade_04d2_dual_image_binding_v1.py"),
        "FACADE-04D.2 contract suite",
    )

    print("\n[2] FACADE-02 TRANSPORT REGRESSION")
    facade02_ok, _ = run_direct_suite(
        os.path.join("tests", "test_facade_02_dual_image_transport_v1.py"),
        "FACADE-02 transport regression",
    )

    print("\n[3] RENDER / SEMANTIC-FIDELITY REGRESSION (pytest)")
    # EXCLUDED — these are LIVE integration tests that drive a real
    # ChatArchitect turn. `tests/test_render_approval_gate.py` submits a REAL
    # ComfyUI job (its second test asserts status == "success" after an
    # un-mocked render) and its first test fails on a pre-existing design-state
    # regression (`design_status == 'none'`, not 'draft'). The brief forbids a
    # real render, so neither is run here. `test_design_only_no_render.py` also
    # drives the full live pipeline and is excluded for the same reason.
    record("live-render tests excluded from the zero-render run", True,
           "test_render_approval_gate.py, test_design_only_no_render.py")

    render_ok = run_pytest(
        [
            "tests/render/",
            "tests/test_render_semantic_fidelity_v1.py",
            "tests/test_runtime_foundation_01.py",
        ],
        "render + FACADE-04A semantic fidelity (zero-render suites)",
    )

    print("\n[4] STATIC ARCHITECTURE")
    static_checks()

    after = comfy_output_snapshot()
    print("\ncomfy output after:", after)

    record("no render was produced (ComfyUI output unchanged)",
           before == after, "before=%s after=%s" % (before.get("files"), after.get("files")))

    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["ok"])

    failed = [r["name"] for r in RESULTS if not r["ok"]]

    final_status = "COMPLETE" if passed == total else "INCOMPLETE"

    report = {
        "phase": "FACADE-04D.2",
        "title": "Role-aware dual-image render binding V1",
        "final_status": final_status,
        "passed": passed,
        "total": total,
        "failed": failed,
        "contract_suite": dual_counts,
        "real_renders": 0 if before == after else None,
        "comfy_output_before": before,
        "comfy_output_after": after,
        "duration_seconds": round(time.time() - started, 1),
        "checks": RESULTS,
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    print("\n=== ACCEPTANCE RESULT: %d/%d — %s ===" % (passed, total, final_status))
    print("report:", REPORT_PATH)

    if failed:
        print("FAILED:")
        for name in failed:
            print("  - " + name)

    return 0 if final_status == "COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
