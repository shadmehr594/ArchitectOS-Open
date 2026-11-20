# -*- coding: utf-8 -*-
# ==========================================================
# FACADE-04D.3C-0 — USER OPT-IN + LIVE RENDER READINESS (CONTRACT SUITE)
#
# Proves the complete request path WITHOUT rendering:
#
#   UI proxy (ui/app.py) -> core API boundary (app.py)
#     -> context["conditioned_render"] + context["references"]["A"/"B"]
#       -> ChatArchitect dispatch (render-approval + FACADE-04A gates intact)
#         -> ImageHandler.handle_image_generate(conditioned=...)
#           -> RenderRuntime.render(..., conditioned=...)   [executor MOCKED]
#
# The dispatch cases run in FRESH SUBPROCESSES: ChatArchitect state is a
# process-wide singleton, so two dispatch cases in one process contaminate
# each other's routing. Each case therefore reports a JSON verdict.
#
#   * NO ComfyUI job, NO GPU load, NO inference, NO image generation.
#   * Run DIRECTLY (script-style):
#       .venv/Scripts/python.exe tests/test_facade_04d3c0_conditioned_optin_v1.py
# ==========================================================

import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

FIXTURES = r"D:\ArchitectOS_FACADE_TEST_IMAGES"
A_IMAGE = os.path.join(FIXTURES, "A_STYLE.jpg")
B_IMAGE = os.path.join(FIXTURES, "B01_RAW.jpg")

WORKFLOW_DIR = os.path.join(PROJECT_ROOT, "core", "render", "workflows")

CORE_PORT = 5198
os.environ["ARCHITECTOS_CORE_API_HOST"] = "127.0.0.1"
os.environ["ARCHITECTOS_CORE_API_PORT"] = str(CORE_PORT)

import logging  # noqa: E402

logging.getLogger("werkzeug").setLevel(logging.ERROR)

from core.render import dual_image_conditioning_v1 as COND  # noqa: E402
from core.render.workflow_selector import WorkflowSelector  # noqa: E402

RENDER_TEXT = "یه ویلای مدرن با نمای شیشه و بتن رندر کن"


# ==========================================================
# SUBPROCESS DISPATCH CASES
# ==========================================================

def _dual_context(conditioned):
    return {
        "references": {
            "geometry_authority": "target_building",
            "A": {"present": True, "role": "facade_reference", "authority": "appearance_only",
                  "path": A_IMAGE, "asset_id": "asset_a_fixture", "filename": "A_STYLE.jpg"},
            "B": {"present": True, "role": "target_building", "authority": "geometry",
                  "path": B_IMAGE, "asset_id": "asset_b_fixture", "filename": "B01_RAW.jpg"},
        },
        "image_count": 2,
        "conditioned_render": conditioned,
    }


class _FakeBrain:
    def process(self, text, context=None):
        return {"result": {}, "architectural_intent": {}}


def run_case(case):
    """One dispatch case in a FRESH process. Prints a single CASE_JSON line."""

    import core.chat.chat_architect as CA
    import core.vision.facade_reference_vision_provider_v1 as VP

    VP.analyze_ab_references = lambda refs, context=None: {
        "A": {"analysis_status": "OK"},
        "B": {"analysis_status": "OK"},
        "roles": {"A": "facade_reference", "B": "target_building",
                  "geometry_authority": "target_building"},
    }

    if case == "blocked_fidelity":
        CA.validate_render_fidelity = lambda text, contract=None: {
            "contract": "RenderSemanticFidelityV1", "status": "BLOCKED",
            "reason_code": "TEST_BLOCKED", "may_proceed_to_render": False,
        }
    else:
        CA.validate_render_fidelity = lambda text, contract=None: {
            "contract": "RenderSemanticFidelityV1", "status": "PASS",
            "reason_code": "OK", "may_proceed_to_render": True,
        }

    chat = CA.ChatArchitect(_FakeBrain())

    executed = {}
    render_calls = {}

    runtime = chat.image_handler.render_runtime

    def fake_execute(workflow, engine):
        executed["workflow"] = workflow
        executed["engine"] = engine
        executed["called"] = True
        return {"status": "success", "images": [{"filename": "mock_out.png"}]}

    runtime.executor.execute = fake_execute
    runtime.result_bridge.resolve = lambda ctx: {"status": "success",
                                                 "image": {"filename": "mock_out.png"}}

    original_render = runtime.render

    def render_spy(*args, **kwargs):
        render_calls["kwargs"] = kwargs
        result = original_render(*args, **kwargs)
        render_calls["result"] = result
        return result

    runtime.render = render_spy

    handler_calls = []
    original_handler = chat.image_handler.handle_image_generate

    def handler_spy(*args, **kwargs):
        handler_calls.append(kwargs)
        return original_handler(*args, **kwargs)

    chat.image_handler.handle_image_generate = handler_spy

    if case == "no_refs":
        context = {"references": None, "image_count": 0, "conditioned_render": True}
    elif case == "conditioned":
        context = _dual_context(True)
    elif case == "default":
        context = _dual_context(False)
    elif case == "blocked_fidelity":
        context = _dual_context(True)
    else:
        raise SystemExit("unknown case: " + case)

    chat_result = chat._handle_internal(RENDER_TEXT, context=context)

    runtime_result = render_calls.get("result") or {}
    submitted = executed.get("workflow") or {}

    verdict = {
        "case": case,
        "handler_calls": len(handler_calls),
        "handler_conditioned": (handler_calls[-1].get("conditioned") if handler_calls else None),
        "handler_bindings": bool(handler_calls[-1].get("image_bindings")) if handler_calls else None,
        "handler_image_asset_status": ((handler_calls[-1].get("image_asset") or {}).get("status")
                                       if handler_calls else None),
        "render_kwargs_conditioned": render_calls.get("kwargs", {}).get("conditioned"),
        "render_kwargs_has_bindings": bool(render_calls.get("kwargs", {}).get("image_bindings")),
        "runtime_workflow": runtime_result.get("workflow"),
        "runtime_status": runtime_result.get("status"),
        "runtime_conditioning": runtime_result.get("conditioning"),
        "executor_called": bool(executed.get("called")),
        "submitted": {
            "node300": ((submitted.get("300") or {}).get("inputs") or {}).get("image"),
            "node302": ((submitted.get("302") or {}).get("inputs") or {}).get("image"),
            "model": ((submitted.get("210") or {}).get("inputs") or {}).get("model"),
            "latent": ((submitted.get("210") or {}).get("inputs") or {}).get("latent_image"),
            "positive": ((submitted.get("210") or {}).get("inputs") or {}).get("positive"),
            "negative": ((submitted.get("210") or {}).get("inputs") or {}).get("negative"),
            "has_uso": any(isinstance(n, dict) and n.get("class_type") == "USOStyleReference"
                           for n in submitted.values()),
            "has_cnet": any(isinstance(n, dict) and n.get("class_type") == "ControlNetApplyAdvanced"
                            for n in submitted.values()),
            "clip_name_304": ((submitted.get("304") or {}).get("inputs") or {}).get("clip_name"),
        },
        "chat_type": (chat_result or {}).get("type"),
        "chat_reason": (chat_result or {}).get("reason"),
    }

    print("CASE_JSON:" + json.dumps(verdict, ensure_ascii=False))


def run_dispatch_case(case):
    proc = subprocess.run([sys.executable, "-u", os.path.abspath(__file__), "--case", case],
                          cwd=PROJECT_ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=10800)
    out = (proc.stdout or "") + (proc.stderr or "")
    for line in out.splitlines():
        if line.startswith("CASE_JSON:"):
            return json.loads(line[len("CASE_JSON:"):])
    return {"case": case, "error": "no verdict", "rc": proc.returncode, "tail": out[-400:]}


# ==========================================================
# RESULTS
# ==========================================================

RESULTS = []


def check(name, condition, detail=""):
    ok = bool(condition)
    RESULTS.append((name, ok, detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  | " + detail) if detail else ""))
    return ok


def sha256_file(path):
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_workflow(name):
    with open(os.path.join(WORKFLOW_DIR, name), encoding="utf-8") as handle:
        return json.load(handle)


# ==========================================================
# [0] STATIC
# ==========================================================

def section_static():

    print("\n[0] STATIC: UI CONTROL + SERVER FIELD + PRESERVATION")

    with open(os.path.join(PROJECT_ROOT, "ui", "templates", "index.html"), encoding="utf-8") as h:
        html = h.read()
    with open(os.path.join(PROJECT_ROOT, "ui", "static", "app.js"), encoding="utf-8") as h:
        js = h.read()
    with open(os.path.join(PROJECT_ROOT, "app.py"), encoding="utf-8") as h:
        py = h.read()
    with open(os.path.join(PROJECT_ROOT, "ui", "routes", "chat_routes.py"), encoding="utf-8") as h:
        routes = h.read()
    with open(os.path.join(PROJECT_ROOT, "core", "chat", "chat_architect.py"), encoding="utf-8") as h:
        ca = h.read()

    check("UI has a conditionedToggle checkbox",
          'id="conditionedToggle"' in html and 'type="checkbox"' in html)
    check("UI control is DISABLED by default",
          'id="conditionedToggle" type="checkbox" disabled>' in html)
    check("UI control is never pre-checked",
          'disabled checked' not in html)

    check("client appends conditioned_render only when checked AND >=2 images",
          'conditionedToggle.checked && files.length >= 2' in js
          and 'form.append("conditioned_render", "1")' in js)
    check("client clears+disables the control below 2 images",
          "function syncConditionedToggle()" in js
          and "toggle.disabled = !eligible;" in js
          and "if (!eligible) toggle.checked = false;" in js)
    check("syncConditionedToggle is wired into onAttach and clearAttachment",
          js.count("syncConditionedToggle();") >= 2)

    check("server reads ONLY the explicit field",
          'request.form.get("conditioned_render"' in py)
    check("server never derives the flag from message text",
          not any(s in py for s in ('conditioned_render" in message',
                                    'conditioned_render" in text',
                                    "conditioned_render = re.",
                                    "conditioned_render = message")))

    check("server rejects conditioned without BOTH images",
          "conditioned_render_requires_both_images" in py
          and '_image_references.get("A")' in py
          and '_image_references.get("B")' in py)
    check("file-less requests forward the flag so it can be rejected",
          "_conditioned_field = request.form.get(\"conditioned_render\")" in routes)

    check("FACADE-04D.2 workflow sha256 unchanged since 04D.3B-2",
          sha256_file(os.path.join(WORKFLOW_DIR, "flux_img2img_dual.json"))
          == "36189746a43a476f789944413d3944e3560c22c987cde1a462bc673470a04da9")

    cond = load_workflow(COND.CONDITIONED_WORKFLOW)
    check("conditioned workflow still statically verifies",
          COND.verify_conditioning_graph(cond)["status"] == "wired")
    check("conditioned workflow model parameters untouched",
          cond["210"]["inputs"]["denoise"] == 0.3
          and cond["311"]["inputs"]["strength"] == 0.8
          and cond["311"]["inputs"]["end_percent"] == 0.8
          and cond["320"]["inputs"]["strength_model"] == 1.0)

    guard = ca.index("DUAL-IMAGE RENDER BLOCKED:")
    dispatch = ca.index("conditioned=_dual_conditioned,")
    approval = ca.index('design_status != "approved" and design_render_request:')
    check("FACADE-04A gate precedes the conditioned dispatch", guard < dispatch)
    check("render-approval gate precedes the conditioned dispatch", approval < dispatch)


# ==========================================================
# [1] REAL HTTP BOUNDARY
# ==========================================================

def section_http_boundary():

    print("\n[1] REAL HTTP BOUNDARY -> context['conditioned_render']")

    from werkzeug.serving import make_server

    import app as CORE

    captured = []

    def spy(input_text, context=None):
        captured.append(context)
        return {"type": "chat", "result": "ok", "status": "success"}

    CORE.chat._handle_internal = spy

    srv = make_server("127.0.0.1", CORE_PORT, CORE.app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    for _ in range(100):
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/status" % CORE_PORT, timeout=1).read()
            break
        except urllib.error.HTTPError:
            break
        except Exception:
            time.sleep(0.1)

    from ui.app import app as UI_APP

    client = UI_APP.test_client()

    def ft(path):
        with open(path, "rb") as handle:
            return (io.BytesIO(handle.read()), os.path.basename(path))

    def post_dual(conditioned=None):
        data = {"text": RENDER_TEXT, "image_a": ft(A_IMAGE), "image_b": ft(B_IMAGE)}
        if conditioned is not None:
            data["conditioned_render"] = conditioned
        return client.post("/api/chat", data=data, content_type="multipart/form-data")

    def post_single(conditioned=None):
        data = {"text": RENDER_TEXT, "image": ft(B_IMAGE)}
        if conditioned is not None:
            data["conditioned_render"] = conditioned
        return client.post("/api/chat", data=data, content_type="multipart/form-data")

    try:
        captured.clear()
        resp = post_dual("1")
        ctx = (captured[-1] if captured else {}) or {}
        check("dual + opt-in -> HTTP 200", resp.status_code == 200, "status=%s" % resp.status_code)
        check("context['conditioned_render'] is True",
              ctx.get("conditioned_render") is True, str(ctx.get("conditioned_render")))
        refs = ctx.get("references") or {}
        check("context references carry BOTH roles",
              bool(refs.get("A")) and bool(refs.get("B")))

        captured.clear()
        resp = post_dual()
        ctx = (captured[-1] if captured else {}) or {}
        check("dual WITHOUT opt-in -> conditioned_render is False",
              resp.status_code == 200 and ctx.get("conditioned_render") is False,
              "status=%s value=%s" % (resp.status_code, ctx.get("conditioned_render")))

        captured.clear()
        resp = post_dual("0")
        ctx = (captured[-1] if captured else {}) or {}
        check("explicit conditioned_render=0 stays False",
              ctx.get("conditioned_render") is False)

        resp = post_single("1")
        body = resp.get_json() or {}
        check("single image + opt-in -> HTTP 400", resp.status_code == 400,
              "status=%s" % resp.status_code)
        check("error is conditioned_render_requires_both_images",
              body.get("error") == "conditioned_render_requires_both_images",
              str(body.get("error")))
        check("UI-readable response.message present",
              bool((body.get("response") or {}).get("message")))

        resp = client.post("/api/chat", data={"text": RENDER_TEXT, "conditioned_render": "1"},
                           content_type="multipart/form-data")
        body = resp.get_json() or {}
        check("no images + opt-in -> HTTP 400", resp.status_code == 400,
              "status=%s" % resp.status_code)
        check("no images -> explicit error code",
              body.get("error") == "conditioned_render_requires_both_images")

        resp = client.post("/api/chat", json={"text": RENDER_TEXT, "conditioned_render": True})
        body = resp.get_json() or {}
        check("JSON conditioned request -> HTTP 400", resp.status_code == 400,
              "status=%s" % resp.status_code)
        check("JSON conditioned -> explicit error code",
              body.get("error") == "conditioned_render_requires_both_images")

        captured.clear()
        resp = client.post("/api/chat", json={"text": RENDER_TEXT})
        ctx = (captured[-1] if captured else {}) or {}
        check("plain JSON chat -> conditioned_render is False (default OFF)",
              ctx.get("conditioned_render") is False, str(ctx.get("conditioned_render")))

        captured.clear()
        resp = post_single()
        ctx = (captured[-1] if captured else {}) or {}
        check("legacy single-image turn -> 200 and conditioned_render False",
              resp.status_code == 200 and ctx.get("conditioned_render") is False,
              "status=%s value=%s" % (resp.status_code, ctx.get("conditioned_render")))

    finally:
        srv.shutdown()


# ==========================================================
# [2] FULL DISPATCH CHAIN (subprocess-isolated, executor mocked)
# ==========================================================

def section_dispatch_chain():

    print("\n[2] FULL DISPATCH CHAIN (fresh process per case; executor MOCKED)")

    cond = run_dispatch_case("conditioned")
    if cond.get("error"):
        check("conditioned case produced a verdict", False, str(cond)[:300])
        return

    check("conditioned: handle_image_generate called once", cond["handler_calls"] == 1,
          str(cond["handler_calls"]))
    check("conditioned: handler received conditioned=True",
          cond["handler_conditioned"] is True, str(cond["handler_conditioned"]))
    check("conditioned: handler received role bindings", cond["handler_bindings"] is True)
    check("conditioned: handler received a ready IMAGE B asset",
          cond["handler_image_asset_status"] == "ready", str(cond["handler_image_asset_status"]))

    check("conditioned: RenderRuntime.render received conditioned=True",
          cond["render_kwargs_conditioned"] is True, str(cond["render_kwargs_conditioned"]))
    check("conditioned: RenderRuntime.render received image_bindings",
          cond["render_kwargs_has_bindings"] is True)
    check("conditioned: runtime selected the CONDITIONED workflow",
          cond["runtime_workflow"] == COND.CONDITIONED_WORKFLOW, str(cond["runtime_workflow"]))
    check("conditioned: executor invoked (mocked)", cond["executor_called"] is True)

    sub = cond["submitted"]
    check("conditioned: node 300 carries IMAGE B", bool(sub["node300"]), str(sub["node300"]))
    check("conditioned: node 302 carries IMAGE A", bool(sub["node302"]), str(sub["node302"]))
    check("conditioned: IMAGE A did not reach node 300", sub["node300"] != sub["node302"])
    check("conditioned: 210.model <- [322, 0]", sub["model"] == ["322", 0], str(sub["model"]))
    check("conditioned: 210.latent_image <- [301, 0]", sub["latent"] == ["301", 0], str(sub["latent"]))
    check("conditioned: 210.positive <- [311, 0]", sub["positive"] == ["311", 0], str(sub["positive"]))
    check("conditioned: 210.negative <- [311, 1]", sub["negative"] == ["311", 1], str(sub["negative"]))
    check("conditioned: submitted graph has USOStyleReference", sub["has_uso"] is True)
    check("conditioned: submitted graph has ControlNetApplyAdvanced", sub["has_cnet"] is True)
    check("conditioned: node 304 uses SigLIP",
          sub["clip_name_304"] == COND.SIGLIP_ENCODER, str(sub["clip_name_304"]))

    trace = cond.get("runtime_conditioning") or {}
    check("conditioned: trace conditioning_wired True", trace.get("conditioning_wired") is True)
    check("conditioned: trace conditioning_runtime_verified False",
          trace.get("conditioning_runtime_verified") is False)
    check("conditioned: trace conditioning_effect_verified False",
          trace.get("conditioning_effect_verified") is False)

    # ---- default (opt-in absent) ----------------------------------------
    default = run_dispatch_case("default")
    if default.get("error"):
        check("default case produced a verdict", False, str(default)[:300])
        return

    check("default: handler received conditioned=False",
          default["handler_conditioned"] is False, str(default["handler_conditioned"]))
    check("default: runtime selected the UNCONDITIONED workflow",
          default["runtime_workflow"] == COND.UNCONDITIONED_WORKFLOW,
          str(default["runtime_workflow"]))
    check("default: conditioning trace is None", default["runtime_conditioning"] is None)
    check("default: submitted graph has NO USOStyleReference",
          default["submitted"]["has_uso"] is False)
    check("default: submitted graph has NO ControlNetApplyAdvanced",
          default["submitted"]["has_cnet"] is False)


# ==========================================================
# [3] FAIL-CLOSED
# ==========================================================

def section_fail_closed():

    print("\n[3] FAIL-CLOSED (no silent downgrade)")

    blocked = run_dispatch_case("blocked_fidelity")
    if blocked.get("error"):
        check("blocked case produced a verdict", False, str(blocked)[:300])
    else:
        check("BLOCKED fidelity -> render_blocked",
              blocked["chat_type"] == "render_blocked", str(blocked["chat_type"]))
        check("BLOCKED fidelity -> reason dual_image_render_not_ready",
              blocked["chat_reason"] == "dual_image_render_not_ready", str(blocked["chat_reason"]))
        check("BLOCKED fidelity -> handle_image_generate NEVER called",
              blocked["handler_calls"] == 0, str(blocked["handler_calls"]))
        check("BLOCKED fidelity -> executor NEVER called", blocked["executor_called"] is False)

    norefs = run_dispatch_case("no_refs")
    if norefs.get("error"):
        check("no_refs case produced a verdict", False, str(norefs)[:300])
    else:
        check("conditioned without A/B -> runtime refuses (conditioning_requires_dual_binding)",
              norefs["runtime_status"] == "conditioning_requires_dual_binding",
              str(norefs["runtime_status"]))
        check("conditioned without A/B -> executor NEVER called",
              norefs["executor_called"] is False)
        check("conditioned without A/B -> did NOT fall back to an unconditioned workflow",
              norefs["runtime_workflow"] is None, str(norefs["runtime_workflow"]))


# ==========================================================
# [4] ROUTING / DEFAULTS REGRESSION
# ==========================================================

def section_routing():

    print("\n[4] ROUTING / DEFAULTS REGRESSION")

    import inspect

    sel = WorkflowSelector()
    image = {"filename": "x.png"}
    bindings = {"target_building": {"node_id": "300", "filename": "b.png"}}

    check("text2img -> flux.json",
          sel.select({"engine": "flux", "mode": "text2img"}) == "flux.json")
    check("single img2img -> flux_img2img.json",
          sel.select({"engine": "flux", "mode": "img2img", "image": image}) == "flux_img2img.json")
    check("dual default -> flux_img2img_dual.json",
          sel.select({"engine": "flux", "mode": "img2img", "image": image,
                      "image_bindings": bindings}) == COND.UNCONDITIONED_WORKFLOW)
    check("dual + conditioned -> conditioned workflow",
          sel.select({"engine": "flux", "mode": "img2img", "image": image,
                      "image_bindings": bindings, "conditioned": True}) == COND.CONDITIONED_WORKFLOW)
    check("conditioned never implied by dual_image alone",
          sel.select({"engine": "flux", "mode": "img2img", "image": image,
                      "dual_image": True}) == COND.UNCONDITIONED_WORKFLOW)

    from config import runtime_config as RC
    check("config workflow list in sync with selector",
          set(RC.REQUIRED_WORKFLOW_FILES) == set(sel.available_workflows()))

    from core.render.render_runtime import RenderRuntime
    sig = inspect.signature(RenderRuntime.render)
    check("RenderRuntime.render conditioned defaults to False",
          sig.parameters["conditioned"].default is False)
    check("RenderRuntime.render image_bindings defaults to None",
          sig.parameters["image_bindings"].default is None)

    from core.chat.handlers.image_handler import ImageHandler
    sig2 = inspect.signature(ImageHandler.handle_image_generate)
    check("ImageHandler.handle_image_generate conditioned defaults to False",
          sig2.parameters["conditioned"].default is False)


# ==========================================================
# MAIN
# ==========================================================

def main():

    print("=== FACADE-04D.3C-0 CONDITIONED OPT-IN CONTRACT SUITE ===")

    for required in (A_IMAGE, B_IMAGE):
        if not os.path.isfile(required):
            print("MISSING FIXTURE: " + required)
            return 2

    section_static()
    section_routing()
    section_dispatch_chain()
    section_fail_closed()
    section_http_boundary()

    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)

    print("\n=== RESULT: %d/%d checks passed ===" % (passed, total))

    failed = [name for name, ok, _ in RESULTS if not ok]
    if failed:
        print("FAILED:")
        for name in failed:
            print("  - " + name)
        return 1

    print("ALL FACADE-04D.3C-0 CONDITIONED OPT-IN CHECKS PASSED")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--case":
        run_case(sys.argv[2])
        sys.exit(0)
    sys.exit(main())
