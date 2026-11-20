# -*- coding: utf-8 -*-
# ==========================================================
# FACADE-04D.3B-2 — ACCEPTANCE RUNNER
# REAL USO STYLE + CONTROLNET GEOMETRY WORKFLOW INTEGRATION
#
#   * ZERO renders: the ComfyUI output directory is snapshotted before and
#     after and must be unchanged. No job is ever submitted.
#   * Every render submission in the suites below is MOCKED.
#   * The optional /object_info step is a READ-ONLY GET; it is skipped when
#     ComfyUI is not running, and it never submits anything.
#
# Run:
#   .venv/Scripts/python.exe -u tools/run_facade_04d3b2_acceptance.py
# ==========================================================

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
COMFY_OBJECT_INFO = "http://127.0.0.1:8188/object_info"
REPORT_PATH = os.path.join(PROJECT_ROOT, "tools", "acceptance_facade_04d3b2_report.json")

RESULTS = []


def record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  | " + detail) if detail else ""))
    return bool(ok)


def comfy_snapshot():
    if not os.path.isdir(COMFY_OUTPUT):
        return {"exists": False, "files": None, "newest": None, "newest_mtime": None}
    files = [f for f in os.listdir(COMFY_OUTPUT) if os.path.isfile(os.path.join(COMFY_OUTPUT, f))]
    newest, newest_mtime = None, None
    for name in files:
        m = os.path.getmtime(os.path.join(COMFY_OUTPUT, name))
        if newest_mtime is None or m > newest_mtime:
            newest, newest_mtime = name, m
    return {"exists": True, "files": len(files), "newest": newest, "newest_mtime": newest_mtime}


def run_direct(rel_path, label):
    path = os.path.join(PROJECT_ROOT, rel_path)
    if not os.path.isfile(path):
        record(label + " suite present", False, "missing " + rel_path)
        return False, None
    proc = subprocess.run([PY, "-u", path], cwd=PROJECT_ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=10800)
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
    targets = [os.path.join(PROJECT_ROOT, p) for p in rel_paths]
    targets = [t for t in targets if os.path.exists(t)]
    proc = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + targets,
                          cwd=PROJECT_ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=10800)
    out = (proc.stdout or "") + (proc.stderr or "")
    m = re.search(r"(\d+)\s+passed", out)
    passed = int(m.group(1)) if m else 0
    failed = re.search(r"(\d+)\s+failed", out)
    ok = proc.returncode == 0 and passed > 0 and not failed
    record(label, ok, "passed=%d failed=%s rc=%s" % (passed, failed.group(1) if failed else 0, proc.returncode))
    return ok


def static_checks():
    print("\n[STATIC] WORKFLOW INTEGRITY")

    wf_dir = os.path.join(PROJECT_ROOT, "core", "render", "workflows")
    cond = json.load(open(os.path.join(wf_dir, "flux_img2img_dual_conditioned.json"), encoding="utf-8"))
    dual = json.load(open(os.path.join(wf_dir, "flux_img2img_dual.json"), encoding="utf-8"))

    record("conditioned workflow is an API prompt",
           all(isinstance(n, dict) and "class_type" in n and "inputs" in n for n in cond.values()))
    record("conditioned workflow has 21 nodes", len(cond) == 21, "n=%d" % len(cond))
    record("FACADE-04D.2 workflow node set unchanged",
           set(dual.keys()) == {"202", "204", "205", "206", "212", "210", "208", "9",
                                "300", "301", "302", "303", "304"})
    record("FACADE-04D.2 workflow has no conditioning nodes",
           not ({"305", "306", "307", "310", "311", "320", "321", "322"} & set(dual.keys())))
    record("no stale CLIP-ViT-H encoder in the conditioned graph",
           "clip_vision_h.safetensors" not in json.dumps(cond))

    from core.render import dual_image_conditioning_v1 as COND
    record("conditioned graph statically verifies",
           COND.verify_conditioning_graph(cond)["status"] == "wired")
    mrep = COND.verify_conditioning_models()
    record("all five conditioning models present on disk (size-checked)",
           mrep["status"] == "ready", str(mrep["missing"]) + str(mrep["invalid"]))


def live_object_info():
    """READ-ONLY GET. Skips cleanly if ComfyUI is not reachable."""

    print("\n[LIVE] /object_info (read-only; no submission)")
    import urllib.request

    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(COMFY_OBJECT_INFO, timeout=10800) as response:
            info = json.load(response)
    except Exception as exc:  # noqa: BLE001
        record("ComfyUI /object_info reachable", False,
               "%s (skipped — no submission attempted)" % type(exc).__name__)
        return None

    def combo_options(entry):
        if not isinstance(entry, list) or not entry:
            return None
        if isinstance(entry[0], list):
            return entry[0]
        if len(entry) > 1 and isinstance(entry[1], dict):
            return entry[1].get("options")
        return None

    loaders = [
        ("LoraLoaderModelOnly", "lora_name", "uso-flux1-dit-lora-v1.safetensors"),
        ("ModelPatchLoader", "name", "uso-flux1-projector-v1.safetensors"),
        ("CLIPVisionLoader", "clip_name", "sigclip_vision_patch14_384.safetensors"),
        ("ControlNetLoader", "control_net_name", "flux1-dev-controlnet-union-pro-2.0-fp8.safetensors"),
        ("LoadDA3Model", "model_name", "depth_anything_3_small.safetensors"),
    ]
    summary = {}
    for cls, inp, fname in loaders:
        entry = (((info.get(cls) or {}).get("input") or {}).get("required") or {}).get(inp)
        opts = combo_options(entry)
        ok = bool(opts) and fname in opts
        summary[cls] = {"input": inp, "filename": fname, "listed": ok}
        record("LIVE %s.%s lists %s" % (cls, inp, fname), ok, str(opts))

    classes = ["UNETLoader", "DualCLIPLoader", "VAELoader", "CLIPTextEncode", "KSampler",
               "VAEDecode", "SaveImage", "LoadImage", "VAEEncode", "CLIPVisionLoader",
               "CLIPVisionEncode", "LoraLoaderModelOnly", "ModelPatchLoader",
               "USOStyleReference", "LoadDA3Model", "DA3Inference", "DA3Render",
               "ControlNetLoader", "ControlNetApplyAdvanced"]
    missing = [c for c in classes if c not in info]
    record("LIVE all 19 required node classes present", missing == [], str(missing))
    return summary


def main():

    started = time.time()
    print("=== FACADE-04D.3B-2 ACCEPTANCE ===")
    print("python:", PY)

    before = comfy_snapshot()
    print("comfy output before:", before)

    print("\n[1] CONDITIONED WORKFLOW CONTRACT SUITE")
    cond_ok, cond_counts = run_direct(
        os.path.join("tests", "test_facade_04d3b2_conditioned_workflow_v1.py"),
        "FACADE-04D.3B-2 contract suite")

    print("\n[2] FACADE-04D.2 REGRESSION")
    run_direct(os.path.join("tests", "test_facade_04d2_dual_image_binding_v1.py"),
               "FACADE-04D.2 binding regression")

    print("\n[3] FACADE-02 TRANSPORT REGRESSION")
    run_direct(os.path.join("tests", "test_facade_02_dual_image_transport_v1.py"),
               "FACADE-02 transport regression")

    print("\n[4] RENDER / SEMANTIC-FIDELITY REGRESSION (zero-render suites)")
    # test_render_approval_gate.py and test_design_only_no_render.py are LIVE tests
    # that drive real renders — deliberately EXCLUDED.
    record("live-render tests excluded from the zero-render run", True,
           "test_render_approval_gate.py, test_design_only_no_render.py")
    run_pytest(["tests/render/", "tests/test_render_semantic_fidelity_v1.py",
                "tests/test_runtime_foundation_01.py"],
               "render + FACADE-04A semantic fidelity")

    static_checks()
    live = live_object_info()

    after = comfy_snapshot()
    print("\ncomfy output after:", after)
    record("no render was produced (ComfyUI output unchanged)", before == after,
           "before=%s after=%s" % (before.get("files"), after.get("files")))

    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["ok"])
    failed = [r["name"] for r in RESULTS if not r["ok"]]
    status = "COMPLETE" if passed == total else "INCOMPLETE"

    report = {
        "phase": "FACADE-04D.3B-2",
        "title": "Real USO style + ControlNet geometry workflow integration",
        "final_status": status,
        "passed": passed,
        "total": total,
        "failed": failed,
        "contract_suite": cond_counts,
        "real_renders": 0 if before == after else None,
        "comfy_output_before": before,
        "comfy_output_after": after,
        "live_object_info": live,
        "duration_seconds": round(time.time() - started, 1),
        "checks": RESULTS,
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    print("\n=== ACCEPTANCE RESULT: %d/%d — %s ===" % (passed, total, status))
    print("report:", REPORT_PATH)
    if failed:
        print("FAILED:")
        for name in failed:
            print("  - " + name)
    return 0 if status == "COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
