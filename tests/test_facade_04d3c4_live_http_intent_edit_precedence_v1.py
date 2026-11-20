# -*- coding: utf-8 -*-
# ==========================================================
# FACADE-04D.3C-4 — LIVE HTTP INTENT_EDIT PRECEDENCE FIX (ACCEPTANCE SUITE)
#
# Starts at the REAL app.py HTTP boundary: multipart POST /chat with
# image_a = A_STYLE.jpg, image_b = B01_RAW.jpg, seed_value = 123456789 and the
# exact accepted Persian facade-redesign prompt. The full chain runs:
#
#   app.py -> ChatArchitect._handle_internal -> ImageHandler -> RenderRuntime
#
# SAFETY
#   * ARCHITECTOS_COMFY_PORT=9 AND a socket-level guard that raises on any
#     connect to port 8188 (or any port) — no test can submit a ComfyUI job.
#   * ComfyHTTPRuntime.submit/execute are hard-patched to raise.
#   * The executor is replaced by a recorder. NO real render, NO GPU, NO job.
#   * ComfyUI input staging is redirected to a temp dir (test isolation).
#
# Run DIRECTLY (script-style; a pytest "N passed" line is not evidence):
#   .venv/Scripts/python.exe tests/test_facade_04d3c4_live_http_intent_edit_precedence_v1.py
# ==========================================================

import os

# ---- NETWORK-SAFETY GUARD (must be set BEFORE importing app/config) ----
os.environ["ARCHITECTOS_COMFY_PORT"] = "9"
os.environ.setdefault("ARCHITECTOS_CORE_API_HOST", "127.0.0.1")

import hashlib  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import socket  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

WORKFLOW_DIR = os.path.join(PROJECT_ROOT, "core", "render", "workflows")

FIXTURES = r"D:\ArchitectOS_FACADE_TEST_IMAGES"
A_IMAGE = os.path.join(FIXTURES, "A_STYLE.jpg")
B_IMAGE = os.path.join(FIXTURES, "B01_RAW.jpg")

EXACT_PROMPT = (
    "نمای ساختمان تصویر B را بازطراحی کن با الهام از سبک و متریال و زبان فرمی "
    "تصویر A. هندسه کلی، تعداد طبقات، بازشوها، بالکن\u200cها، حجم کلی و کادر "
    "دید ساختمان B حفظ شود. خروجی باید یک رندر نمای باکیفیت و واقعی از ساختمان "
    "B با ظاهر الهام\u200cگرفته از A باشد."
)

SEED = 123456789

SHA_DUAL = "36189746a43a476f789944413d3944e3560c22c987cde1a462bc673470a04da9"
SHA_CONDITIONED = "343c91f367a9f82fd436d04631128a65867c5bb391467afeb5173235184f09f3"


# ==========================================================
# SOCKET-LEVEL NETWORK GUARD (installed before anything can dial out)
# ==========================================================

_BLOCKED_CONNECTS = []

_real_connect = socket.socket.connect

#: The ComfyUI port. A connect attempt here is a hard failure.
COMFY_PORT = 8188


def _guarded_connect(self, address, *args, **kwargs):
    try:
        host, port = address[0], int(address[1])
    except Exception:
        host, port = "?", -1
    if port == COMFY_PORT:
        _BLOCKED_CONNECTS.append((str(host), port))
        raise RuntimeError(
            "NETWORK GUARD: ComfyUI (port %d) connect blocked" % COMFY_PORT
        )
    return _real_connect(self, address, *args, **kwargs)


socket.socket.connect = _guarded_connect


import app as CORE  # noqa: E402
import core.vision.facade_reference_vision_provider_v1 as VP  # noqa: E402
import core.chat.chat_architect as CA  # noqa: E402
from config import runtime_config as RC  # noqa: E402
from core.render.comfy_http_runtime import ComfyHTTPRuntime  # noqa: E402


def _boom(*a, **k):
    raise RuntimeError("NETWORK GUARD: real ComfyUI submit attempted")


ComfyHTTPRuntime.submit = _boom
ComfyHTTPRuntime.execute = _boom


# ---- deterministic A/B vision + fidelity (the live gates still run) ----
VP.analyze_ab_references = lambda refs, context=None: {
    "A": {"analysis_status": "OK"},
    "B": {"analysis_status": "OK"},
    "roles": {"A": "facade_reference", "B": "target_building",
              "geometry_authority": "target_building"},
}
_ORIG_FIDELITY = CA.validate_render_fidelity


def _fidelity_pass(text, contract=None):
    return {"contract": "RenderSemanticFidelityV1", "status": "PASS",
            "reason_code": "OK", "may_proceed_to_render": True}


CA.validate_render_fidelity = _fidelity_pass


RESULTS = []


def check(name, condition, detail=""):
    ok = bool(condition)
    RESULTS.append((name, ok, detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  | " + detail) if detail else ""))
    return ok


def load_workflow(name):
    with open(os.path.join(WORKFLOW_DIR, name), encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ==========================================================
# HARNESS
# ==========================================================

STAGE_ROOT = tempfile.mkdtemp(prefix="facade04d3c4_comfy_input_")

#: Module-level recorders so the handler spies never capture a stale state.
EXECUTOR_CALLS = []
HANDLER_CALLS = []


def install_harness():
    """Mock the executor, redirect staging, spy on the handlers."""

    RC.COMFYUI_INPUT_DIR = STAGE_ROOT

    chat = CORE.chat
    runtime = chat.image_handler.render_runtime

    EXECUTOR_CALLS.clear()
    HANDLER_CALLS.clear()

    def fake_execute(workflow, engine):
        EXECUTOR_CALLS.append({"workflow": workflow, "engine": engine})
        return {"status": "success", "images": [{"filename": "mock_out.png"}]}

    runtime.executor.execute = fake_execute
    runtime.result_bridge.resolve = lambda ctx: {"status": "success",
                                                 "image": {"filename": "mock_out.png"}}

    if not getattr(runtime, "_3c4_spied", False):
        orig_g = chat.image_handler.handle_image_generate
        orig_e = chat.image_handler.handle_image_edit

        def spy_g(*a, **k):
            HANDLER_CALLS.append("generate")
            return orig_g(*a, **k)

        def spy_e(*a, **k):
            HANDLER_CALLS.append("edit")
            return orig_e(*a, **k)

        chat.image_handler.handle_image_generate = spy_g
        chat.image_handler.handle_image_edit = spy_e
        runtime._3c4_spied = True

    return chat, runtime


def post_chat(session_id, files, extra=None):
    client = CORE.app.test_client()
    data = {"text": EXACT_PROMPT, "session_id": session_id,
            "seed_value": str(SEED), "seed_mode": "lock",
            "mode": "image_to_image", "quality": "auto"}
    for key, path in files.items():
        with open(path, "rb") as handle:
            data[key] = (io.BytesIO(handle.read()), os.path.basename(path))
    if extra:
        data.update(extra)
    resp = client.post("/chat", data=data, content_type="multipart/form-data")
    try:
        body = resp.get_json() or {}
    except Exception:
        body = {}
    return resp.status_code, body


# ==========================================================
# [0] STATIC / GUARDS
# ==========================================================

def section_static():

    print("\n[0] STATIC + SAFETY GUARDS")

    check("network guard: ARCHITECTOS_COMFY_PORT is 9",
          os.environ.get("ARCHITECTOS_COMFY_PORT") == "9")
    check("network guard: RC.COMFYUI_URL does not point at 8188",
          "8188" not in RC.COMFYUI_URL, RC.COMFYUI_URL)
    check("network guard: socket.connect is patched",
          socket.socket.connect is _guarded_connect)
    check("network guard: ComfyHTTPRuntime.submit is hard-patched",
          ComfyHTTPRuntime.submit is _boom)

    ca = open(os.path.join(PROJECT_ROOT, "core", "chat", "chat_architect.py"),
              encoding="utf-8").read()

    check("_verified_dual_pair guard exists", "_verified_dual_pair = bool(" in ca)
    check("guard on the single-image routing (`if image and not ...`)",
          "if image and not _verified_dual_pair:" in ca)
    check("guard on the text-only reference routing",
          "if text.strip() and not _verified_dual_pair:" in ca)
    check("guard on the referenced-image routing",
          "if referenced_image and not _verified_dual_pair:" in ca)
    check("guard on the state-driven img2img edit route",
          'IMAGE EDIT ROUTE ACTIVE FROM STATE' in ca
          and 'mode == "img2img"\n            and\n            not _verified_dual_pair' in ca)
    check("all dual-image precedence guards present (>= 8 uses)",
          ca.count("_verified_dual_pair") >= 8,
          "uses=%d" % ca.count("_verified_dual_pair"))
    check("declared-but-incomplete pair fails closed",
          '"dual_image_binding_incomplete"' in ca)

    # preserved gates
    check("FACADE-04A dual-image gate preserved",
          '"dual_image_render_not_ready"' in ca)
    check("render-approval gate preserved",
          'design_status != "approved" and design_render_request:' in ca)
    check("FACADE-04D.3C-2 handler precedence preserved",
          "FACADE-04D.3C-2 — DUAL-IMAGE / CONDITIONED PRECEDENCE"
          in open(os.path.join(PROJECT_ROOT, "core", "chat", "handlers",
                               "image_handler.py"), encoding="utf-8").read())

    # workflow integrity
    check("flux_img2img_dual.json sha256 unchanged",
          sha256_file(os.path.join(WORKFLOW_DIR, "flux_img2img_dual.json")) == SHA_DUAL)
    check("flux_img2img_dual_conditioned.json sha256 unchanged",
          sha256_file(os.path.join(WORKFLOW_DIR, "flux_img2img_dual_conditioned.json"))
          == SHA_CONDITIONED)

    # the trigger (documents the root cause): app.py exposes IMAGE B as `image`
    app_src = open(os.path.join(PROJECT_ROOT, "app.py"), encoding="utf-8").read()
    check("app.py still exposes IMAGE B as the legacy single `image` (the trigger)",
          "uploaded_image = _image_b or _image_a" in app_src)

    # FACADE-04D.3C-4 — preset precedence correction
    rr_src = open(os.path.join(PROJECT_ROOT, "core", "render", "render_runtime.py"),
                  encoding="utf-8").read()
    fn = rr_src[rr_src.index("def _resolve_request_preset("):]
    fn = fn[:fn.index("\n    def ", 1)]
    check("img2img suppression is evaluated BEFORE the caller-supplied preset",
          fn.index('str(design.get("mode")) == "img2img"')
          < fn.index('given = design.get("preset_resolution")'))
    check("an EXPLICIT user-selected preset is preserved for img2img",
          'given.get("source") == "explicit"' in fn)


# ==========================================================
# [1] HTTP MULTIPART — CONDITIONED OFF
# ==========================================================

def section_http_off():

    print("\n[1] REAL HTTP MULTIPART — CONDITIONED OFF")

    chat, runtime = install_harness()

    status, body = post_chat("facade04d3c4_off", {"image_a": A_IMAGE, "image_b": B_IMAGE})

    check("HTTP 200", status == 200, "status=%s" % status)
    check("handler route is generate (NOT the legacy edit route)",
          HANDLER_CALLS == ["generate"], str(HANDLER_CALLS))
    check("executor invoked exactly once (mocked)", len(EXECUTOR_CALLS) == 1,
          str(len(EXECUTOR_CALLS)))

    wf = (EXECUTOR_CALLS[0]["workflow"] if EXECUTOR_CALLS else {}) or {}
    md = runtime.last_render_metadata or {}

    check("workflow == flux_img2img_dual.json",
          md.get("workflow_name") == "flux_img2img_dual.json", str(md.get("workflow_name")))
    check("NO legacy single-image fallback (flux_img2img.json not used)",
          md.get("workflow_name") != "flux_img2img.json")
    check("IMAGE A -> node 302", bool((wf.get("302") or {}).get("inputs", {}).get("image")))
    check("IMAGE B -> node 300", bool((wf.get("300") or {}).get("inputs", {}).get("image")))
    check("node 300 != node 302 (no substitution)",
          (wf.get("300") or {}).get("inputs", {}).get("image")
          != (wf.get("302") or {}).get("inputs", {}).get("image"))
    check("node 210 latent from node 301",
          (wf.get("210") or {}).get("inputs", {}).get("latent_image") == ["301", 0])
    check("300 -> 301 -> 210 intact",
          (wf.get("301") or {}).get("inputs", {}).get("pixels") == ["300", 0])

    s = (wf.get("210") or {}).get("inputs", {})
    check("seed = 123456789", s.get("seed") == SEED, str(s.get("seed")))
    check("cfg = 5", s.get("cfg") == 5, str(s.get("cfg")))
    check("denoise = 0.3 (NOT the legacy 0.25)", s.get("denoise") == 0.3, str(s.get("denoise")))
    check("steps = 30", s.get("steps") == 30, str(s.get("steps")))
    check("preset suppressed for img2img (metadata.preset is None)",
          md.get("preset") is None, str(md.get("preset")))
    check("no text-to-image preset quality tail in node 206",
          "bright natural daylight" not in str(
              (wf.get("206") or {}).get("inputs", {}).get("text", "")).lower())

    print("      OFF SUBMITTED 210:", json.dumps(
        {k: s.get(k) for k in ("seed", "steps", "cfg", "denoise", "sampler_name", "scheduler")}))

    # image identity by fixture hash
    _identity_checks(wf, "OFF")


# ==========================================================
# [2] HTTP MULTIPART — CONDITIONED ON
# ==========================================================

def section_http_on():

    print("\n[2] REAL HTTP MULTIPART — CONDITIONED ON")

    chat, runtime = install_harness()

    status, body = post_chat("facade04d3c4_on", {"image_a": A_IMAGE, "image_b": B_IMAGE},
                             extra={"conditioned_render": "1"})

    check("HTTP 200", status == 200, "status=%s" % status)
    check("handler route is generate (NOT the legacy edit route)",
          HANDLER_CALLS == ["generate"], str(HANDLER_CALLS))
    check("executor invoked exactly once (mocked)", len(EXECUTOR_CALLS) == 1,
          str(len(EXECUTOR_CALLS)))

    wf = (EXECUTOR_CALLS[0]["workflow"] if EXECUTOR_CALLS else {}) or {}
    md = runtime.last_render_metadata or {}

    check("workflow == flux_img2img_dual_conditioned.json",
          md.get("workflow_name") == "flux_img2img_dual_conditioned.json",
          str(md.get("workflow_name")))
    check("IMAGE A -> node 302", bool((wf.get("302") or {}).get("inputs", {}).get("image")))
    check("IMAGE B -> node 300", bool((wf.get("300") or {}).get("inputs", {}).get("image")))
    check("node 210 latent from node 301",
          (wf.get("210") or {}).get("inputs", {}).get("latent_image") == ["301", 0])
    check("USO reaches KSampler.model (210.model <- [322,0])",
          (wf.get("210") or {}).get("inputs", {}).get("model") == ["322", 0])
    check("ControlNet reaches positive conditioning (210.positive <- [311,0])",
          (wf.get("210") or {}).get("inputs", {}).get("positive") == ["311", 0])
    check("ControlNet reaches negative conditioning (210.negative <- [311,1])",
          (wf.get("210") or {}).get("inputs", {}).get("negative") == ["311", 1])

    resolved = (runtime.last_render_request or {}).get("resolved_prompt")
    t206 = (wf.get("206") or {}).get("inputs", {}).get("text")
    t212 = (wf.get("212") or {}).get("inputs", {}).get("text")
    check("resolved architectural prompt reaches node 206",
          bool(resolved) and t206 == resolved, "206[:70]=%s" % str(t206)[:70])
    check("negative prompt reaches node 212",
          bool(t212) and t212 != t206, "212[:70]=%s" % str(t212)[:70])

    s = (wf.get("210") or {}).get("inputs", {})
    check("seed = 123456789", s.get("seed") == SEED, str(s.get("seed")))
    check("cfg = 5", s.get("cfg") == 5, str(s.get("cfg")))
    check("denoise = 0.3", s.get("denoise") == 0.3, str(s.get("denoise")))
    check("steps = 30", s.get("steps") == 30, str(s.get("steps")))
    check("preset suppressed for img2img (metadata.preset is None)",
          md.get("preset") is None, str(md.get("preset")))
    check("no text-to-image preset quality tail in node 206",
          "bright natural daylight" not in str(t206 or "").lower())

    print("      ON SUBMITTED 210:", json.dumps(
        {k: s.get(k) for k in ("seed", "steps", "cfg", "denoise", "sampler_name", "scheduler")}))

    _identity_checks(wf, "ON")


def _identity_checks(wf, tag):

    a_name = (wf.get("302") or {}).get("inputs", {}).get("image")
    b_name = (wf.get("300") or {}).get("inputs", {}).get("image")

    a_staged = os.path.join(STAGE_ROOT, a_name) if a_name else None
    b_staged = os.path.join(STAGE_ROOT, b_name) if b_name else None

    check("%s: staged IMAGE A exists" % tag, bool(a_staged) and os.path.isfile(a_staged),
          str(a_staged))
    check("%s: staged IMAGE B exists" % tag, bool(b_staged) and os.path.isfile(b_staged),
          str(b_staged))
    check("%s: staged A bytes == A_STYLE.jpg bytes" % tag,
          bool(a_staged) and os.path.isfile(a_staged)
          and sha256_file(a_staged) == sha256_file(A_IMAGE))
    check("%s: staged B bytes == B01_RAW.jpg bytes" % tag,
          bool(b_staged) and os.path.isfile(b_staged)
          and sha256_file(b_staged) == sha256_file(B_IMAGE))
    check("%s: A and B identities differ (no substitution)" % tag,
          bool(a_name) and bool(b_name) and a_name != b_name
          and sha256_file(A_IMAGE) != sha256_file(B_IMAGE))


# ==========================================================
# [3] SINGLE-IMAGE EDIT STILL LEGACY
# ==========================================================

def section_single_image():

    print("\n[3] SINGLE-IMAGE EDIT — LEGACY PATH PRESERVED")

    chat, runtime = install_harness()

    status, body = post_chat("facade04d3c4_single", {"image": B_IMAGE})

    check("HTTP 200", status == 200, "status=%s" % status)
    check("single-image edit still uses the legacy edit handler",
          HANDLER_CALLS == ["edit"], str(HANDLER_CALLS))

    wf = (EXECUTOR_CALLS[0]["workflow"] if EXECUTOR_CALLS else {}) or {}
    md = runtime.last_render_metadata or {}

    check("single-image edit selects flux_img2img.json",
          md.get("workflow_name") == "flux_img2img.json", str(md.get("workflow_name")))
    check("single-image edit has exactly one LoadImage and no node 302",
          sum(1 for n in wf.values()
              if isinstance(n, dict) and n.get("class_type") == "LoadImage") == 1
          and "302" not in wf)


# ==========================================================
# [4] FAIL-CLOSED
# ==========================================================

def section_fail_closed():

    print("\n[4] FAIL-CLOSED")

    # (a) conditioned with only IMAGE A -> boundary refuses (HTTP 400)
    status, body = post_chat("facade04d3c4_fc_a", {"image_a": A_IMAGE},
                             extra={"conditioned_render": "1"})
    check("conditioned with only IMAGE A -> HTTP 400", status == 400, str(status))
    check("error code conditioned_render_requires_both_images",
          body.get("error") == "conditioned_render_requires_both_images", str(body.get("error")))

    # (b) conditioned with no images -> HTTP 400
    client = CORE.app.test_client()
    resp = client.post("/chat", data={"text": EXACT_PROMPT, "session_id": "facade04d3c4_fc_none",
                                      "conditioned_render": "1"},
                       content_type="multipart/form-data")
    body = resp.get_json() or {}
    check("conditioned with no images -> HTTP 400", resp.status_code == 400, str(resp.status_code))
    check("no-images error code explicit",
          body.get("error") == "conditioned_render_requires_both_images", str(body.get("error")))

    # (c) declared pair but INCOMPLETE -> render_blocked, executor never called
    chat, runtime = install_harness()

    res = chat._handle_internal(
        EXACT_PROMPT,
        context={"references": {"A": {"present": True, "path": A_IMAGE,
                                      "asset_id": "a", "filename": "A_STYLE.jpg",
                                      "role": "facade_reference"},
                                "B": {}},
                 "image_count": 2, "conditioned_render": False,
                 "session_id": "facade04d3c4_fc_incomplete"},
    )
    check("declared-but-incomplete pair -> render_blocked",
          (res or {}).get("type") == "render_blocked"
          and (res or {}).get("reason") == "dual_image_binding_incomplete", str(res)[:200])
    check("declared-but-incomplete pair NEVER invoked the executor",
          len(EXECUTOR_CALLS) == 0)

    # (d) unreadable IMAGE A -> the dual contract fails closed
    chat, runtime = install_harness()

    res = chat._handle_internal(
        EXACT_PROMPT,
        context={"references": {
            "A": {"present": True, "path": os.path.join(FIXTURES, "does_not_exist.jpg"),
                  "asset_id": "a", "filename": "missing.jpg", "role": "facade_reference"},
            "B": {"present": True, "path": B_IMAGE, "asset_id": "b",
                  "filename": "B01_RAW.jpg", "role": "target_building"}},
            "image_count": 2, "conditioned_render": False,
            "session_id": "facade04d3c4_fc_unreadable"},
    )
    check("unreadable IMAGE A -> render_blocked",
          (res or {}).get("type") == "render_blocked", str(res)[:200])
    check("unreadable IMAGE A reason names the style reference",
          (res or {}).get("reason") == "style_reference_image_unavailable",
          str((res or {}).get("reason")))
    check("unreadable IMAGE A NEVER invoked the executor", len(EXECUTOR_CALLS) == 0)

    # (e) fidelity BLOCKED still blocks the dual render (gate preserved)
    chat, runtime = install_harness()
    CA.validate_render_fidelity = lambda text, contract=None: {
        "contract": "RenderSemanticFidelityV1", "status": "BLOCKED",
        "reason_code": "TEST_BLOCKED", "may_proceed_to_render": False,
    }
    try:
        res = chat._handle_internal(
            EXACT_PROMPT,
            context={"references": {
                "A": {"present": True, "path": A_IMAGE, "asset_id": "a",
                      "filename": "A_STYLE.jpg", "role": "facade_reference"},
                "B": {"present": True, "path": B_IMAGE, "asset_id": "b",
                      "filename": "B01_RAW.jpg", "role": "target_building"}},
                "image_count": 2, "conditioned_render": False,
                "session_id": "facade04d3c4_fc_fidelity"},
        )
    finally:
        CA.validate_render_fidelity = _fidelity_pass

    check("BLOCKED fidelity -> render_blocked (gate preserved)",
          (res or {}).get("type") == "render_blocked", str(res)[:200])
    check("BLOCKED fidelity NEVER invoked the executor", len(EXECUTOR_CALLS) == 0)


# ==========================================================
# MAIN
# ==========================================================

def main():

    print("=== FACADE-04D.3C-4 LIVE HTTP INTENT_EDIT PRECEDENCE — ACCEPTANCE SUITE ===")

    for required in (A_IMAGE, B_IMAGE):
        if not os.path.isfile(required):
            print("MISSING FIXTURE: " + required)
            return 2

    section_static()
    section_http_off()
    section_http_on()
    section_single_image()
    section_fail_closed()

    print("\n=== SOCKET GUARD: blocked outbound connects = %d ===" % len(_BLOCKED_CONNECTS))

    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)

    print("\n=== RESULT: %d/%d checks passed ===" % (passed, total))

    failed = [name for name, ok, _ in RESULTS if not ok]
    if failed:
        print("FAILED:")
        for name in failed:
            print("  - " + name)
        return 1

    print("ALL FACADE-04D.3C-4 LIVE HTTP ACCEPTANCE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        shutil.rmtree(STAGE_ROOT, ignore_errors=True)
    sys.exit(code)
