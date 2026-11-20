# ==========================================================
# FACADE-03 — REAL DUAL-IMAGE ARCHITECTURAL VISION VALIDATION
#
# Scope: REAL vision analysis only. No generation, no render, no ComfyUI.
#
# Path exercised:
#   real UI proxy -> real core API boundary (FACADE-02) -> context["references"]
#     -> analyze_ab_references()  (the EXISTING 2D-5 analyzer + real Ollama)
#       -> per-role structured architectural analysis
#
# Also verifies SHA-256 integrity between the ORIGINAL test files and the
# STORED upload copies the vision provider actually read.
#
# Run:  .venv/Scripts/python.exe tests/test_facade_03_real_dual_image_vision_v1.py
# ==========================================================

import hashlib
import io
import json
import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

TEST_DIR = r"D:\ArchitectOS_FACADE_TEST_IMAGES"
OUT_DIR = os.path.join(PROJECT_ROOT, "docs", "audit")

os.environ["ARCHITECTOS_CORE_API_HOST"] = "127.0.0.1"
os.environ["ARCHITECTOS_CORE_API_PORT"] = "5199"
logging.getLogger("werkzeug").setLevel(logging.ERROR)

from werkzeug.serving import make_server  # noqa: E402

import app as CORE  # noqa: E402

from ui.app import app as UI_APP  # noqa: E402

UI_CLIENT = UI_APP.test_client()

RESULTS = []
SUMMARY = {}


def check(name, condition, detail=""):
    ok = bool(condition)
    RESULTS.append((name, ok, detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  | " + detail) if detail else ""), flush=True)
    return ok


CAPTURED = []


def _install_recorder():
    def _spy(input_text, context=None):
        CAPTURED.append({"text": input_text, "context": context})
        return {"type": "chat", "result": "ok", "status": "success"}

    CORE.chat._handle_internal = _spy


def _start_core():
    srv = make_server("127.0.0.1", 5199, CORE.app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    for _ in range(100):
        try:
            urllib.request.urlopen("http://127.0.0.1:5199/status", timeout=1).read()
            return srv
        except urllib.error.HTTPError:
            return srv
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("core server not ready")


def _file_tuple(path):
    with open(path, "rb") as fh:
        return (io.BytesIO(fh.read()), os.path.basename(path))


def _sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def post_dual(text, a_path, b_path):
    return UI_CLIENT.post(
        "/api/chat",
        data={"text": text, "image_a": _file_tuple(a_path), "image_b": _file_tuple(b_path)},
        content_type="multipart/form-data",
    )


def post_single(text, path):
    return UI_CLIENT.post(
        "/api/chat",
        data={"text": text, "image": _file_tuple(path)},
        content_type="multipart/form-data",
    )


STYLE = os.path.join(TEST_DIR, "A_STYLE.jpg")
TARGETS = ["B01_RAW.jpg", "B02_RAW.jpg", "B03_RAW.jpg",
           "B04_RAW.jpg", "B05_RAW.jpg", "B06_RAW.png"]
TEXT = "این ساختمان را با استایل و مصالح عکس اول بازطراحی کن"


def _digest(analysis, keys):
    return {k: analysis.get(k) for k in keys}


def run_pair(target_name, analyze_ab):
    target = os.path.join(TEST_DIR, target_name)
    CAPTURED.clear()
    resp = post_dual(TEXT, STYLE, target)
    check("%s :: dual upload HTTP 200" % target_name, resp.status_code == 200,
          "status=%s" % resp.status_code)

    ctx = CAPTURED[-1]["context"] if CAPTURED else {}
    refs = ctx.get("references") if isinstance(ctx, dict) else None
    check("%s :: references present" % target_name, isinstance(refs, dict))
    if not isinstance(refs, dict):
        return

    # ---- SHA-256 integrity: original test file vs STORED upload copy ----
    a_stored = (refs.get("A") or {}).get("path")
    b_stored = (refs.get("B") or {}).get("path")
    check("%s :: A stored copy exists" % target_name,
          bool(a_stored) and os.path.isfile(a_stored))
    check("%s :: B stored copy exists" % target_name,
          bool(b_stored) and os.path.isfile(b_stored))
    if a_stored and b_stored and os.path.isfile(a_stored) and os.path.isfile(b_stored):
        check("%s :: SHA-256 A original == stored" % target_name,
              _sha256(STYLE) == _sha256(a_stored))
        check("%s :: SHA-256 B original == stored" % target_name,
              _sha256(target) == _sha256(b_stored))

    # ---- REAL dual-image architectural vision ----
    t0 = time.time()
    ab = analyze_ab(refs)
    elapsed = round(time.time() - t0, 1)

    check("%s :: A/B analysis produced" % target_name,
          isinstance(ab, dict) and bool(ab.get("A")) and bool(ab.get("B")))
    if not (isinstance(ab, dict) and ab.get("A") and ab.get("B")):
        return

    A, B = ab["A"], ab["B"]

    check("%s :: A is real (not PROVIDER_UNAVAILABLE)" % target_name,
          A.get("analysis_status") != "PROVIDER_UNAVAILABLE",
          "A=%s" % A.get("analysis_status"))
    check("%s :: B is real (not PROVIDER_UNAVAILABLE)" % target_name,
          B.get("analysis_status") != "PROVIDER_UNAVAILABLE",
          "B=%s" % B.get("analysis_status"))

    check("%s :: A role/source = reference_image" % target_name,
          A.get("source_type") == "reference_image")
    check("%s :: B role/source = base_building_image" % target_name,
          B.get("source_type") == "base_building_image")

    check("%s :: geometry_authority = target_building" % target_name,
          (ab.get("roles") or {}).get("geometry_authority") == "target_building")

    # ---- A/B separation: the two analyses must be independent ----
    keys = ("facade_style", "materials", "color_palette", "windows",
            "visible_floor_count", "symmetry", "ornament_level",
            "classical_features", "modern_features")
    a_dig = _digest(A, keys)
    b_dig = _digest(B, keys)
    differs = a_dig != b_dig
    check("%s :: A and B observations are independent (not identical)" % target_name,
          differs)

    SUMMARY[target_name] = {
        "elapsed_s": elapsed,
        "model": A.get("model"),
        "A": {
            "status": A.get("analysis_status"),
            "facade_style": A.get("facade_style"),
            "style_confidence": A.get("style_confidence"),
            "materials": [m.get("type") for m in A.get("materials") or []],
            "color_palette": A.get("color_palette"),
            "classical_features": A.get("classical_features"),
            "modern_features": A.get("modern_features"),
            "visible_floor_count": A.get("visible_floor_count"),
            "symmetry": A.get("symmetry"),
            "ornament_level": A.get("ornament_level"),
            "windows": A.get("windows"),
            "balconies": A.get("balconies"),
            "roof_features_raw": (A.get("unsupported_inferences"),),
            "uncertainties": A.get("uncertainties"),
        },
        "B": {
            "status": B.get("analysis_status"),
            "facade_style": B.get("facade_style"),
            "style_confidence": B.get("style_confidence"),
            "materials": [m.get("type") for m in B.get("materials") or []],
            "color_palette": B.get("color_palette"),
            "classical_features": B.get("classical_features"),
            "modern_features": B.get("modern_features"),
            "visible_floor_count": B.get("visible_floor_count"),
            "symmetry": B.get("symmetry"),
            "ornament_level": B.get("ornament_level"),
            "windows": B.get("windows"),
            "balconies": B.get("balconies"),
            "uncertainties": B.get("uncertainties"),
        },
    }
    print("        A: style=%s floors=%s sym=%s | B: style=%s floors=%s sym=%s (%.1fs)"
          % (A.get("facade_style"), A.get("visible_floor_count"), A.get("symmetry"),
             B.get("facade_style"), B.get("visible_floor_count"), B.get("symmetry"),
             elapsed), flush=True)


def main():
    _install_recorder()
    srv = _start_core()

    from core.vision.facade_reference_vision_provider_v1 import analyze_ab_references

    print("\n=== FACADE-03 REAL DUAL-IMAGE ARCHITECTURAL VISION ===\n", flush=True)
    print("[1] SIX A/B PAIRS — real Ollama vision (A=A_STYLE.jpg)\n", flush=True)
    for target in TARGETS:
        run_pair(target, analyze_ab_references)

    print("\n[2] SINGLE-IMAGE REGRESSION (no A/B references => no dual analysis)", flush=True)
    CAPTURED.clear()
    resp = post_single("این ساختمان چند طبقه است؟", os.path.join(TEST_DIR, "B01_RAW.jpg"))
    check("single :: HTTP 200", resp.status_code == 200, "status=%s" % resp.status_code)
    ctx = CAPTURED[-1]["context"] if CAPTURED else {}
    check("single :: references is None (unchanged)", ctx.get("references") is None)
    check("single :: dual analysis is a no-op without A/B",
          analyze_ab_references(ctx.get("references")) == {})

    srv.shutdown()

    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("\n=== RESULT: %d/%d checks passed ===" % (passed, total), flush=True)
    failed = [n for n, ok, _ in RESULTS if not ok]
    if failed:
        print("FAILED:", failed, flush=True)

    with open(os.path.join(OUT_DIR, "FACADE_03_VISION_SUMMARY.json"), "w", encoding="utf-8") as fh:
        json.dump(SUMMARY, fh, ensure_ascii=False, indent=2)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
