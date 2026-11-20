# ==========================================================
# FACADE-02 — DUAL IMAGE TRANSPORT / A-B ROLE BINDING VALIDATION
#
# Scope: TRANSPORT + ROLE BINDING ONLY.
#   * no vision inference
#   * no image generation
#   * no rendering, no ComfyUI
#   * downstream components are MOCKED (ChatArchitect._handle_internal)
#
# This harness exercises the REAL path:
#
#   real UI proxy (ui/app.py -> ui/routes/chat_routes.py)
#     -> HTTP multipart  (image_a / image_b)
#       -> real Core API boundary (app.py chat_api)
#         -> real ChatArchitect entry (ChatArchitect.handle)
#           -> context["references"]  (captured)
#
# and then feeds the captured references to the REAL production consumer
# (core.cognition.architectural_render_instruction_v1.build_render_instruction)
# to prove the A/B role contract is genuinely activated.
#
# The real test images are uploaded over HTTP as real bytes.  A file NAME
# is never treated as proof an image arrived: every assertion compares the
# transported asset's size_bytes with the bytes on disk in the test dir.
#
# Run:  .venv/Scripts/python.exe tests/test_facade_02_dual_image_transport_v1.py
# ==========================================================

import io
import os
import sys
import json
import time
import logging
import threading
import urllib.request
import urllib.error

# Quiet the per-request werkzeug access log so the harness output is readable.
logging.getLogger("werkzeug").setLevel(logging.ERROR)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

TEST_DIR = r"D:\ArchitectOS_FACADE_TEST_IMAGES"

# Dedicated port so the harness never collides with a running instance.
os.environ["ARCHITECTOS_CORE_API_HOST"] = "127.0.0.1"
os.environ["ARCHITECTOS_CORE_API_PORT"] = "5199"

from werkzeug.serving import make_server  # noqa: E402

import app as CORE  # noqa: E402  (real core gateway + real ChatArchitect)


# ==========================================================
# RESULT BOOKKEEPING
# ==========================================================

RESULTS = []


def check(name, condition, detail=""):
    ok = bool(condition)
    RESULTS.append((name, ok, detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  | " + detail) if detail else ""))
    return ok


# ==========================================================
# MOCK THE DOWNSTREAM, KEEP THE ENTRY REAL
#
# `ChatArchitect.handle` stays the REAL public entry.  Only the private
# `_handle_internal` is replaced with a recorder, so nothing downstream
# (vision, LLM, render, ComfyUI) ever runs.
# ==========================================================

CAPTURED = []


def _install_recorder():
    def _spy(input_text, context=None):
        CAPTURED.append({"text": input_text, "context": context})
        return {"type": "chat", "result": "ok", "status": "success"}

    CORE.chat._handle_internal = _spy


# ==========================================================
# CORE SERVER (real HTTP boundary)
# ==========================================================

def _start_core():
    srv = make_server("127.0.0.1", 5199, CORE.app, threaded=True)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    for _ in range(100):
        try:
            urllib.request.urlopen("http://127.0.0.1:5199/status", timeout=1).read()
            return srv
        except urllib.error.HTTPError:
            # Any HTTP response means the server is listening.
            return srv
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("core server did not become ready")


# ==========================================================
# UI PROXY (real front door the browser talks to)
# ==========================================================

from ui.app import app as UI_APP  # noqa: E402

UI_CLIENT = UI_APP.test_client()


def _file_tuple(path):
    name = os.path.basename(path)
    with open(path, "rb") as handle:
        data = handle.read()
    return (io.BytesIO(data), name)


def post_pair(text, field_map):
    """POST a multipart turn through the REAL UI proxy to the REAL core API."""
    data = {"text": text}
    for field, path in field_map.items():
        data[field] = _file_tuple(path)
    return UI_CLIENT.post(
        "/api/chat",
        data=data,
        content_type="multipart/form-data",
    )


def post_dual(text, a_path, b_path):
    return post_pair(text, {"image_a": a_path, "image_b": b_path})


def post_single(text, path):
    return post_pair(text, {"image": path})


def last_context():
    if not CAPTURED:
        raise AssertionError("ChatArchitect entry was never reached")
    return CAPTURED[-1]["context"]


def build_contract(references):
    from core.cognition.architectural_render_instruction_v1 import (
        build_render_instruction,
    )

    return build_render_instruction(
        "این ساختمان را با استایل و مصالح عکس مرجع بازطراحی کن",
        references=references,
    )


# ==========================================================
# THE SIX A/B PAIRS
# ==========================================================

STYLE = os.path.join(TEST_DIR, "A_STYLE.jpg")

TARGETS = [
    "B01_RAW.jpg",
    "B02_RAW.jpg",
    "B03_RAW.jpg",
    "B04_RAW.jpg",
    "B05_RAW.jpg",
    "B06_RAW.png",
]

DUAL_TEXT = "این ساختمان را با استایل و مصالح عکس اول بازطراحی کن"


def run_pair(target_name):
    target = os.path.join(TEST_DIR, target_name)
    CAPTURED.clear()

    resp = post_dual(DUAL_TEXT, STYLE, target)
    body = resp.get_json() or {}

    check("pair %s :: HTTP 200" % target_name, resp.status_code == 200,
          "status=%s" % resp.status_code)

    ctx = last_context()
    refs = ctx.get("references") if isinstance(ctx, dict) else None

    check("pair %s :: context['references'] is a dict" % target_name,
          isinstance(refs, dict))

    if not isinstance(refs, dict):
        return

    a = refs.get("A") or {}
    b = refs.get("B") or {}

    check("pair %s :: IMAGE_A.present == true" % target_name, a.get("present") is True)
    check("pair %s :: IMAGE_B.present == true" % target_name, b.get("present") is True)

    check("pair %s :: A.role == facade_reference" % target_name,
          a.get("role") == "facade_reference")
    check("pair %s :: B.role == target_building" % target_name,
          b.get("role") == "target_building")

    check("pair %s :: A.authority == appearance_only" % target_name,
          a.get("authority") == "appearance_only")
    check("pair %s :: B.authority == geometry" % target_name,
          b.get("authority") == "geometry")

    check("pair %s :: geometry_authority == target_building" % target_name,
          refs.get("geometry_authority") == "target_building")

    check("pair %s :: both assets independently identifiable" % target_name,
          bool(a.get("asset_id")) and bool(b.get("asset_id"))
          and a.get("asset_id") != b.get("asset_id")
          and a.get("relative_path") != b.get("relative_path"))

    # REAL BYTES, NOT NAMES — the transported size must equal disk size.
    a_disk = os.path.getsize(STYLE)
    b_disk = os.path.getsize(target)
    check("pair %s :: A bytes == disk (real transport)" % target_name,
          a.get("size_bytes") == a_disk, "%s vs %s" % (a.get("size_bytes"), a_disk))
    check("pair %s :: B bytes == disk (real transport)" % target_name,
          b.get("size_bytes") == b_disk, "%s vs %s" % (b.get("size_bytes"), b_disk))

    # Both images reach the real chat context.
    check("pair %s :: context['image'] (geometry authority) present" % target_name,
          ctx.get("image") is not None)

    # The REAL production consumer activates the A/B contract.
    contract = build_contract(refs)
    c_refs = contract.get("references") or {}
    check("pair %s :: build_render_instruction A/B present" % target_name,
          c_refs.get("A", {}).get("present") is True
          and c_refs.get("B", {}).get("present") is True
          and c_refs.get("geometry_authority") == "target_building")

    print("        body.status=%s | A=%s (%s B) | B=%s (%s B)"
          % (body.get("status"), a.get("filename"), a.get("size_bytes"),
             b.get("filename"), b.get("size_bytes")))


# ==========================================================
# MAIN
# ==========================================================

def main():
    _install_recorder()
    srv = _start_core()
    print("\n=== FACADE-02 DUAL IMAGE TRANSPORT VALIDATION ===\n")

    print("[1] SIX A/B PAIRS (A = A_STYLE.jpg, B = target)")
    for target in TARGETS:
        run_pair(target)

    print("\n[2] SINGLE-IMAGE REGRESSION (legacy `image` field)")
    CAPTURED.clear()
    resp = post_single("این ساختمان چند طبقه است؟", os.path.join(TEST_DIR, "B01_RAW.jpg"))
    check("single :: HTTP 200", resp.status_code == 200, "status=%s" % resp.status_code)
    ctx = last_context()
    check("single :: context['image'] present (legacy path intact)",
          ctx.get("image") is not None)
    check("single :: context['references'] is None (unchanged contract)",
          ctx.get("references") is None)
    check("single :: image_count == 1", ctx.get("image_count") == 1,
          "image_count=%s" % ctx.get("image_count"))
    single_contract = build_contract(ctx.get("references"))
    s_refs = single_contract.get("references") or {}
    check("single :: builder reports A/B absent (no references supplied)",
          s_refs.get("A", {}).get("present") is False
          and s_refs.get("B", {}).get("present") is False)

    print("\n[3] REJECT MORE THAN TWO IMAGES")
    resp = post_pair(DUAL_TEXT, {
        "image_a": STYLE,
        "image_b": os.path.join(TEST_DIR, "B01_RAW.jpg"),
        "image": os.path.join(TEST_DIR, "B02_RAW.jpg"),
    })
    body = resp.get_json() or {}
    check("reject-3 :: HTTP 400", resp.status_code == 400, "status=%s" % resp.status_code)
    check("reject-3 :: error == too_many_images",
          body.get("error") == "too_many_images", "error=%s" % body.get("error"))
    check("reject-3 :: clear message present", bool(body.get("message")))
    check("reject-3 :: UI-readable response.message present",
          bool((body.get("response") or {}).get("message")))

    print("\n[4] INVALID IMAGE REPORTED TRUTHFULLY")
    resp = post_pair(DUAL_TEXT, {
        "image_a": os.path.join(PROJECT_ROOT, "requirements.txt"),
        "image_b": os.path.join(TEST_DIR, "B01_RAW.jpg"),
    })
    body = resp.get_json() or {}
    check("invalid :: HTTP 400", resp.status_code == 400, "status=%s" % resp.status_code)
    check("invalid :: error == invalid_image",
          body.get("error") == "invalid_image", "error=%s" % body.get("error"))
    check("invalid :: names the failing role A",
          (body.get("invalid_roles") or {}).get("A") is not None,
          "invalid_roles=%s" % body.get("invalid_roles"))
    check("invalid :: UI-readable response.message present",
          bool((body.get("response") or {}).get("message")))

    print("\n[5] FILE NAME IS NOT PROOF (text field named image_a)")
    CAPTURED.clear()
    # `image_a` supplied as a FORM FIELD (a bare name), not a file.
    resp = UI_CLIENT.post(
        "/api/chat",
        data={
            "text": DUAL_TEXT,
            "image_a": "A_STYLE.jpg",
            "image_b": _file_tuple(os.path.join(TEST_DIR, "B01_RAW.jpg")),
        },
        content_type="multipart/form-data",
    )
    check("name-not-proof :: HTTP 200", resp.status_code == 200,
          "status=%s" % resp.status_code)
    ctx = last_context()
    refs = ctx.get("references") if isinstance(ctx, dict) else None
    check("name-not-proof :: no A reference fabricated from a bare name",
          isinstance(refs, dict) and "A" not in refs,
          "references keys=%s" % (sorted(refs.keys()) if isinstance(refs, dict) else refs))
    check("name-not-proof :: B reference still real",
          isinstance(refs, dict) and (refs.get("B") or {}).get("present") is True)

    srv.shutdown()

    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("\n=== RESULT: %d/%d checks passed ===" % (passed, total))

    failed = [name for name, ok, _ in RESULTS if not ok]
    if failed:
        print("FAILED:")
        for name in failed:
            print("  - " + name)
        return 1
    print("ALL FACADE-02 TRANSPORT + ROLE-BINDING CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
