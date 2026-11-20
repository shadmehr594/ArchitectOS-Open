# -*- coding: utf-8 -*-
# ==========================================================
# FACADE-04D.3C-3 — CONDITIONED PROMPT PROPAGATION FIX (CONTRACT SUITE)
#
# Confirmed defect (FACADE-04D.3C-2 observation):
#   In the conditioned dual-image graph the KSampler positive/negative inputs
#   point at ControlNetApplyAdvanced (311), not at a CLIPTextEncode. The
#   prompt injector only read the KSampler's DIRECT conditioning ids, so
#   nodes 206 / 212 kept the workflow template prompt and the resolved
#   architectural prompt never reached the submitted payload.
#
# This suite proves the fix through the REAL RenderRuntime with a MOCKED
# executor, using the EXACT accepted Persian facade-redesign prompt:
#
#   * NO ComfyUI job, NO GPU load, NO inference, NO real render.
#   * Assertions are made on the SUBMITTED mocked API payload, not the source.
#   * Run DIRECTLY (script-style; a pytest "N passed" line is not evidence):
#       .venv/Scripts/python.exe tests/test_facade_04d3c3_conditioned_prompt_propagation_v1.py
# ==========================================================

import copy
import hashlib
import importlib.util
import json
import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Render-stop guard: nothing here may ever reach a real ComfyUI.
os.environ.setdefault("ARCHITECTOS_COMFY_PORT", "9")

WORKFLOW_DIR = os.path.join(PROJECT_ROOT, "core", "render", "workflows")

# Frozen workflow hashes (FACADE-04D.3C-3 must not change any workflow file).
SHA_DUAL = "36189746a43a476f789944413d3944e3560c22c987cde1a462bc673470a04da9"
SHA_CONDITIONED = "343c91f367a9f82fd436d04631128a65867c5bb391467afeb5173235184f09f3"

from core.render.image_workflow_injector import (  # noqa: E402
    ImageWorkflowInjector,
    CONDITIONING_PASSTHROUGH,
    PROMPT_TERMINAL,
)
from core.render.render_runtime import RenderRuntime  # noqa: E402
from core.render.dual_image_conditioning_v1 import (  # noqa: E402
    CONDITIONED_WORKFLOW,
    UNCONDITIONED_WORKFLOW,
    verify_conditioning_graph,
)
from core.render.dual_image_binding_v1 import (  # noqa: E402
    ROLE_A,
    ROLE_B,
    NODE_A,
    NODE_B,
)

# Reuse the FACADE-04D.3C-2 harness so the EXACT accepted Persian prompt and
# the mocked-executor wiring are provably identical (no re-typed prompt).
_prev_spec = importlib.util.spec_from_file_location(
    "_facade_04d3c2_suite",
    os.path.join(PROJECT_ROOT, "tests",
                 "test_facade_04d3c2_dual_image_routing_precedence_v1.py"),
)
prev = importlib.util.module_from_spec(_prev_spec)
_prev_spec.loader.exec_module(prev)

EXACT_PROMPT = prev.EXACT_PROMPT
REQUEST_SEED = prev.REQUEST_SEED


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


def template_default(workflow_name, node_id):
    return load_workflow(workflow_name)[node_id]["inputs"]["text"]


def default_negative():
    return ImageWorkflowInjector().normalize_negative()


# ==========================================================
# [0] STATIC PROOF
# ==========================================================

def section_static():

    print("\n[0] STATIC PROOF (source)")

    inj_src = open(
        os.path.join(PROJECT_ROOT, "core", "render", "image_workflow_injector.py"),
        encoding="utf-8",
    ).read()

    check("ControlNetApplyAdvanced is a supported conditioning passthrough",
          "ControlNetApplyAdvanced" in CONDITIONING_PASSTHROUGH)
    check("WAN passthroughs are still supported",
          {"WanImageToVideo", "WanFirstLastFrameToVideo"} <= set(CONDITIONING_PASSTHROUGH))
    check("the prompt terminal is CLIPTextEncode", PROMPT_TERMINAL == "CLIPTextEncode")

    check("resolve_clip_routes() exists", "def resolve_clip_routes(" in inj_src)
    check("_follow_conditioning_link() exists", "def _follow_conditioning_link(" in inj_src)
    check("inject_prompt() uses resolve_clip_routes()",
          "resolution = self.resolve_clip_routes(" in inj_src)
    check("inject_prompt() returns a resolution report",
          "return workflow, resolution" in inj_src)
    check("inject() flags a blocked injection",
          'result["status"] = "blocked"' in inj_src)

    rr_src = open(
        os.path.join(PROJECT_ROOT, "core", "render", "render_runtime.py"),
        encoding="utf-8",
    ).read()
    check("render_runtime has the prompt-injection fail-closed gate",
          '"prompt_injection_blocked"' in rr_src)

    handler_src = open(
        os.path.join(PROJECT_ROOT, "core", "chat", "handlers", "image_handler.py"),
        encoding="utf-8",
    ).read()
    check("FACADE-04D.3C-2 routing precedence preserved (marker present)",
          "FACADE-04D.3C-2 — DUAL-IMAGE / CONDITIONED PRECEDENCE" in handler_src)
    check("FACADE-04D.3C-2 legacy edit delegation preserved",
          "elif self.is_image_edit_request(text):" in handler_src)

    check("flux_img2img_dual.json sha256 unchanged",
          sha256_file(os.path.join(WORKFLOW_DIR, "flux_img2img_dual.json")) == SHA_DUAL)
    check("flux_img2img_dual_conditioned.json sha256 unchanged",
          sha256_file(os.path.join(WORKFLOW_DIR, "flux_img2img_dual_conditioned.json"))
          == SHA_CONDITIONED)


# ==========================================================
# [1] WORKFLOW INTEGRITY (topology / weights / sampler params)
# ==========================================================

def section_workflow_integrity():

    print("\n[1] CONDITIONED WORKFLOW INTEGRITY")

    wf = load_workflow(CONDITIONED_WORKFLOW)

    check("conditioned workflow still has 21 nodes", len(wf) == 21, "n=%d" % len(wf))

    sampler = wf["210"]["inputs"]
    check("KSampler 210 params unchanged (seed/steps/cfg/denoise)",
          sampler["seed"] == 0 and sampler["steps"] == 30 and sampler["cfg"] == 5
          and sampler["denoise"] == 0.3, str(sampler))
    check("ControlNetApplyAdvanced 311 params unchanged (strength/end_percent)",
          wf["311"]["inputs"]["strength"] == 0.8
          and wf["311"]["inputs"]["end_percent"] == 0.8)
    check("LoRA 320 strength_model unchanged", wf["320"]["inputs"]["strength_model"] == 1.0)

    check("210 is still connected to 311 (positive/negative)",
          sampler["positive"] == ["311", 0] and sampler["negative"] == ["311", 1])
    check("311 positive/negative point at the CLIPTextEncode nodes 206 / 212",
          wf["311"]["inputs"]["positive"] == ["206", 0]
          and wf["311"]["inputs"]["negative"] == ["212", 0])
    check("206 / 212 are CLIPTextEncode",
          wf["206"]["class_type"] == "CLIPTextEncode"
          and wf["212"]["class_type"] == "CLIPTextEncode")
    check("conditioned graph still statically verifies",
          verify_conditioning_graph(wf)["status"] == "wired")


# ==========================================================
# [2] CONDITIONED ON — SUBMITTED MOCKED PAYLOAD
# ==========================================================

def section_conditioned_on(bindings, b_asset):

    print("\n[2] CONDITIONED ON — SUBMITTED MOCKED PAYLOAD")

    handler, runtime, captured, render_calls = prev.make_handler()

    handler.handle_image_generate(
        EXACT_PROMPT,
        image_asset=b_asset,
        image_bindings=bindings,
        conditioned=True,
        render_seed=REQUEST_SEED,
    )

    md = runtime.last_render_metadata or {}
    wf = captured.get("workflow") or {}
    resolved = (runtime.last_render_request or {}).get("resolved_prompt")

    check("conditioned ON selected the conditioned workflow",
          md.get("workflow_name") == CONDITIONED_WORKFLOW, str(md.get("workflow_name")))
    check("executor invoked exactly once (mocked)", captured.get("called") == 1)

    # ---- THE DEFECT: prompt must now reach 206 / 212 ----
    check("SUBMITTED node 206 carries the RESOLVED positive prompt",
          wf["206"]["inputs"]["text"] == resolved and bool(resolved),
          "206[:80]=%s" % str(wf["206"]["inputs"]["text"])[:80])
    check("SUBMITTED node 206 no longer carries the template default",
          wf["206"]["inputs"]["text"]
          != template_default(CONDITIONED_WORKFLOW, "206"))
    check("SUBMITTED node 212 carries the default negative prompt",
          wf["212"]["inputs"]["text"] == default_negative(),
          "212=%s" % str(wf["212"]["inputs"]["text"])[:80])
    check("SUBMITTED node 212 no longer carries the template default",
          wf["212"]["inputs"]["text"]
          != template_default(CONDITIONED_WORKFLOW, "212"))
    check("positive and negative prompts differ (polarity preserved)",
          wf["206"]["inputs"]["text"] != wf["212"]["inputs"]["text"])

    # ---- wiring ----
    s = wf["210"]["inputs"]
    check("SUBMITTED 210.model <- [322, 0] (USO)",
          s["model"] == ["322", 0], str(s.get("model")))
    check("SUBMITTED 210.positive <- [311, 0] (ControlNet)",
          s["positive"] == ["311", 0], str(s.get("positive")))
    check("SUBMITTED 210.negative <- [311, 1] (ControlNet)",
          s["negative"] == ["311", 1], str(s.get("negative")))
    check("SUBMITTED 210.latent_image <- [301, 0] (IMAGE B path)",
          s["latent_image"] == ["301", 0], str(s.get("latent_image")))
    check("SUBMITTED 311.positive <- [206, 0]",
          wf["311"]["inputs"]["positive"] == ["206", 0])
    check("SUBMITTED 311.negative <- [212, 0]",
          wf["311"]["inputs"]["negative"] == ["212", 0])
    check("SUBMITTED 311.image <- [307, 0] (depth from IMAGE B)",
          wf["311"]["inputs"]["image"] == ["307", 0])
    check("SUBMITTED 322.clip_vision_output <- [303, 0] (IMAGE A encoder)",
          wf["322"]["inputs"]["clip_vision_output"] == ["303", 0])
    check("SUBMITTED 300 -> 301 -> 210 intact",
          wf["301"]["inputs"]["pixels"] == ["300", 0]
          and wf["210"]["inputs"]["latent_image"] == ["301", 0])
    check("SUBMITTED graph has USOStyleReference and ControlNetApplyAdvanced",
          wf["322"]["class_type"] == "USOStyleReference"
          and wf["311"]["class_type"] == "ControlNetApplyAdvanced")
    check("SUBMITTED node 304 uses SigLIP",
          wf["304"]["inputs"]["clip_name"].startswith("sigclip"))

    # ---- images ----
    check("IMAGE B remains bound to node 300",
          wf["300"]["inputs"]["image"] == bindings[ROLE_B]["filename"])
    check("IMAGE A remains bound to node 302",
          wf["302"]["inputs"]["image"] == bindings[ROLE_A]["filename"])
    check("IMAGE A did not reach node 300",
          wf["300"]["inputs"]["image"] != bindings[ROLE_A]["filename"])

    # ---- preserved render params ----
    check("submitted seed/steps/cfg/denoise unchanged",
          s["seed"] == REQUEST_SEED and s["steps"] == 30 and s["cfg"] == 5
          and s["denoise"] == 0.3,
          "seed=%s steps=%s cfg=%s denoise=%s" % (s["seed"], s["steps"], s["cfg"], s["denoise"]))

    check("submitted graph still statically verifies",
          verify_conditioning_graph(wf)["status"] == "wired")
    check("prompt injection resolution is `resolved`",
          ((render_calls[-1]["result"].get("injected") or {}).get("prompt_injection") or {})
          .get("status") == "resolved")


# ==========================================================
# [3] CONDITIONED OFF — SUBMITTED MOCKED PAYLOAD
# ==========================================================

def section_conditioned_off(bindings, b_asset):

    print("\n[3] CONDITIONED OFF — SUBMITTED MOCKED PAYLOAD")

    handler, runtime, captured, render_calls = prev.make_handler()

    handler.handle_image_generate(
        EXACT_PROMPT,
        image_asset=b_asset,
        image_bindings=bindings,
        conditioned=False,
        render_seed=REQUEST_SEED,
    )

    md = runtime.last_render_metadata or {}
    wf = captured.get("workflow") or {}
    resolved = (runtime.last_render_request or {}).get("resolved_prompt")

    check("conditioned OFF selected flux_img2img_dual.json",
          md.get("workflow_name") == UNCONDITIONED_WORKFLOW, str(md.get("workflow_name")))
    check("unconditioned: node 206 carries the resolved prompt",
          wf["206"]["inputs"]["text"] == resolved and bool(resolved))
    check("unconditioned: node 212 carries the default negative",
          wf["212"]["inputs"]["text"] == default_negative())
    check("unconditioned: direct KSampler links preserved (positive 206 / negative 212)",
          wf["210"]["inputs"]["positive"] == ["206", 0]
          and wf["210"]["inputs"]["negative"] == ["212", 0])
    check("unconditioned: 210.model <- [202, 0]",
          wf["210"]["inputs"]["model"] == ["202", 0])
    check("unconditioned: IMAGE B -> 300 and IMAGE A -> 302",
          wf["300"]["inputs"]["image"] == bindings[ROLE_B]["filename"]
          and wf["302"]["inputs"]["image"] == bindings[ROLE_A]["filename"])
    check("unconditioned: no USO/ControlNet",
          not any(isinstance(n, dict) and n.get("class_type") in
                  ("USOStyleReference", "ControlNetApplyAdvanced") for n in wf.values()))


# ==========================================================
# [4] SINGLE-IMAGE IMG2IMG + TEXT-TO-IMAGE
# ==========================================================

def section_single_and_text():

    print("\n[4] SINGLE-IMAGE IMG2IMG + TEXT-TO-IMAGE")

    # ---- single-image img2img (legacy flux_img2img.json) ----
    handler, runtime, captured, render_calls = prev.make_handler()
    handler.handle_image_generate(
        EXACT_PROMPT, image={"path": prev.B_IMAGE}, render_seed=REQUEST_SEED,
    )
    md = runtime.last_render_metadata or {}
    wf = captured.get("workflow") or {}
    resolved = (runtime.last_render_request or {}).get("resolved_prompt")

    check("single-image img2img selects flux_img2img.json",
          md.get("workflow_name") == "flux_img2img.json", str(md.get("workflow_name")))
    check("single-image img2img: node 206 carries the resolved prompt",
          wf["206"]["inputs"]["text"] == resolved and bool(resolved))
    check("single-image img2img: node 212 carries the default negative",
          wf["212"]["inputs"]["text"] == default_negative())
    check("single-image img2img: direct links preserved",
          wf["210"]["inputs"]["positive"] == ["206", 0]
          and wf["210"]["inputs"]["negative"] == ["212", 0])
    check("single-image img2img: exactly one LoadImage, no node 302",
          sum(1 for n in wf.values()
              if isinstance(n, dict) and n.get("class_type") == "LoadImage") == 1
          and "302" not in wf)

    # ---- text-to-image ----
    handler, runtime, captured, render_calls = prev.make_handler()
    handler.handle_image_generate("یه ویلای مدرن بساز", render_seed=REQUEST_SEED)
    md = runtime.last_render_metadata or {}
    wf = captured.get("workflow") or {}
    resolved = (runtime.last_render_request or {}).get("resolved_prompt")

    check("text-to-image selects flux.json",
          md.get("workflow_name") == "flux.json", str(md.get("workflow_name")))
    check("text-to-image: node 206 carries the resolved prompt",
          wf["206"]["inputs"]["text"] == resolved and bool(resolved))
    # NOTE: text-to-image runs through the SEPARATE WorkflowInjector, whose
    # default negative string differs from the img2img injector's. Only the
    # polarity invariant is asserted here.
    check("text-to-image: node 212 carries a non-empty negative prompt",
          bool(wf["212"]["inputs"]["text"]))
    check("text-to-image: positive/negative differ (polarity preserved)",
          wf["212"]["inputs"]["text"] != wf["206"]["inputs"]["text"])
    check("text-to-image: direct links preserved",
          wf["210"]["inputs"]["positive"] == ["206", 0]
          and wf["210"]["inputs"]["negative"] == ["212", 0])
    check("text-to-image: no LoadImage",
          not any(isinstance(n, dict) and n.get("class_type") == "LoadImage"
                  for n in wf.values()))


# ==========================================================
# [5] FAIL-CLOSED
# ==========================================================

def section_fail_closed():

    print("\n[5] FAIL-CLOSED (injector + runtime)")

    injector = ImageWorkflowInjector()
    base = load_workflow(CONDITIONED_WORKFLOW)

    # (a) unsupported conditioning node
    wf = copy.deepcopy(base)
    wf["999"] = {"class_type": "ConditioningCombine", "inputs": {}}
    wf["311"]["inputs"]["positive"] = ["999", 0]
    rep = injector.resolve_clip_routes(wf)
    check("unsupported conditioning node -> blocked / unsupported_conditioning_graph",
          rep["status"] == "blocked"
          and "unsupported_conditioning_graph" in rep["errors"], str(rep["errors"]))
    out = injector.inject(wf, "P", {"filename": "b.png"}, {}, image_bindings={
        ROLE_A: {"node_id": NODE_A, "filename": "a.png"},
        ROLE_B: {"node_id": NODE_B, "filename": "b.png"},
    })
    check("unsupported graph -> inject() status blocked", out.get("status") == "blocked")
    check("unsupported graph -> template prompt NOT silently kept",
          out["workflow"]["206"]["inputs"]["text"]
          == template_default(CONDITIONED_WORKFLOW, "206"))

    # (b) ambiguous (missing) conditioning link
    wf = copy.deepcopy(base)
    wf["210"]["inputs"]["positive"] = None
    rep = injector.resolve_clip_routes(wf)
    check("missing conditioning link -> blocked / ambiguous_conditioning_link",
          rep["status"] == "blocked"
          and "ambiguous_conditioning_link" in rep["errors"], str(rep["errors"]))

    # (c) cyclic conditioning graph
    wf = copy.deepcopy(base)
    wf["311"]["inputs"]["positive"] = ["311", 0]
    rep = injector.resolve_clip_routes(wf)
    check("cyclic conditioning graph -> blocked / cyclic_conditioning_graph",
          rep["status"] == "blocked"
          and "cyclic_conditioning_graph" in rep["errors"], str(rep["errors"]))

    # (d) polarity conflict (same terminal for positive and negative)
    wf = copy.deepcopy(base)
    wf["311"]["inputs"]["negative"] = ["206", 0]
    rep = injector.resolve_clip_routes(wf)
    check("polarity conflict -> blocked / conditioning_polarity_conflict",
          rep["status"] == "blocked"
          and "conditioning_polarity_conflict" in rep["errors"], str(rep["errors"]))

    # (e) no KSampler
    wf = copy.deepcopy(base)
    wf.pop("210")
    rep = injector.resolve_clip_routes(wf)
    check("no KSampler -> blocked / no_sampler_conditioning",
          rep["status"] == "blocked"
          and "no_sampler_conditioning" in rep["errors"], str(rep["errors"]))

    # (f) empty workflow
    rep = injector.resolve_clip_routes({})
    check("empty workflow -> blocked / empty_workflow",
          rep["status"] == "blocked" and "empty_workflow" in rep["errors"])

    # (g) runtime-level gate: the executor must never be reached
    stage_root = tempfile.mkdtemp(prefix="facade04d3c3_stage_")
    bindings, b_asset, _ = prev.build_bindings(stage_root)

    broken = copy.deepcopy(base)
    broken["999"] = {"class_type": "ConditioningCombine", "inputs": {}}
    broken["311"]["inputs"]["positive"] = ["999", 0]

    runtime = RenderRuntime()
    captured = {}

    def fake_execute(workflow, engine):
        captured["called"] = True
        return {"status": "success", "images": [{"filename": "x.png"}]}

    runtime.executor.execute = fake_execute
    runtime.result_bridge.resolve = lambda ctx: {"status": "success", "image": {"filename": "x.png"}}
    runtime.loader.load = lambda name: {"status": "loaded", "workflow": copy.deepcopy(broken)}

    res = runtime.render("chat_project",
                         {"mode": "img2img", "prompt": EXACT_PROMPT,
                          "architectural_intent": {"style": "modern", "mode": "img2img"},
                          "project_state": {}},
                         "flux", b_asset, image_bindings=bindings)

    check("runtime: unresolved conditioning -> prompt_injection_blocked",
          res.get("status") == "prompt_injection_blocked", str(res.get("status")))
    check("runtime: executor NEVER invoked", captured.get("called") is None)
    check("runtime: reports the resolution errors",
          bool(((res.get("prompt_injection") or {}).get("errors"))))


# ==========================================================
# [6] DIRECT-LINK / WAN REGRESSION
# ==========================================================

def section_direct_link_regression():

    print("\n[6] DIRECT-LINK / WAN REGRESSION")

    injector = ImageWorkflowInjector()

    single = load_workflow("flux_img2img.json")
    p, n = injector.detect_clip_routes(single)
    check("flux_img2img.json -> positive {206} / negative {212}",
          p == {"206"} and n == {"212"}, "p=%s n=%s" % (p, n))

    text = load_workflow("flux.json")
    p, n = injector.detect_clip_routes(text)
    check("flux.json -> positive {206} / negative {212}",
          p == {"206"} and n == {"212"}, "p=%s n=%s" % (p, n))

    wan = load_workflow("wan_i2v.json")
    p, n = injector.detect_clip_routes(wan)
    check("wan_i2v.json -> traverses WanImageToVideo to {6} / {7}",
          p == {"6"} and n == {"7"}, "p=%s n=%s" % (p, n))

    out = injector.inject(wan, "slow facade camera dolly", {"filename": "approved_facade.png"})
    check("WAN injection still writes the prompt to node 6",
          out["workflow"]["6"]["inputs"]["text"] == "slow facade camera dolly")
    check("WAN injection still binds the source image",
          out["workflow"]["50"]["inputs"]["image"] == "approved_facade.png")

    cond = load_workflow(CONDITIONED_WORKFLOW)
    p, n = injector.detect_clip_routes(cond)
    check("conditioned graph -> traverses ControlNetApplyAdvanced to {206} / {212}",
          p == {"206"} and n == {"212"}, "p=%s n=%s" % (p, n))


# ==========================================================
# MAIN
# ==========================================================

def main():

    print("=== FACADE-04D.3C-3 CONDITIONED PROMPT PROPAGATION — CONTRACT SUITE ===")

    for required in (prev.A_IMAGE, prev.B_IMAGE):
        if not os.path.isfile(required):
            print("MISSING FIXTURE: " + required)
            return 2

    print("EXACT PROMPT:", EXACT_PROMPT[:60], "...")

    section_static()
    section_workflow_integrity()

    stage_root = tempfile.mkdtemp(prefix="facade04d3c3_comfy_input_")
    bindings, b_asset, contract = prev.build_bindings(stage_root)
    check("A/B contract ready (A->302, B->300)",
          bindings[ROLE_A]["node_id"] == NODE_A and bindings[ROLE_B]["node_id"] == NODE_B)

    section_conditioned_on(bindings, b_asset)
    section_conditioned_off(bindings, b_asset)
    section_single_and_text()
    section_fail_closed()
    section_direct_link_regression()

    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)

    print("\n=== RESULT: %d/%d checks passed ===" % (passed, total))

    failed = [name for name, ok, _ in RESULTS if not ok]
    if failed:
        print("FAILED:")
        for name in failed:
            print("  - " + name)
        return 1

    print("ALL FACADE-04D.3C-3 CONDITIONED PROMPT PROPAGATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
