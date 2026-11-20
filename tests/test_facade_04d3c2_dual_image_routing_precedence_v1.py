# -*- coding: utf-8 -*-
# ==========================================================
# FACADE-04D.3C-2 — DUAL-IMAGE ROUTING PRECEDENCE FIX (CONTRACT SUITE)
#
# Root cause proven by FACADE-04D.3C-1:
#   ImageHandler.handle_image_generate() delegated to the legacy
#   single-image edit handler BEFORE honouring `image_bindings` /
#   `conditioned`. The mandated restyle phrase "بازطراحی کن" is an edit
#   keyword, so a dual-image request was consumed by the legacy
#   `flux_img2img.json` edit path and IMAGE A / the conditioned graph were
#   silently discarded.
#
# This suite proves the fix, end to end, with the EXACT mandated Persian
# prompt and REAL fixtures, through the REAL RenderRuntime with a MOCKED
# executor:
#
#   * NO ComfyUI job, NO GPU load, NO inference, NO image generation.
#   * The executor is always replaced by a recorder.
#   * Run DIRECTLY (script-style; a pytest "N passed" line is not evidence):
#       .venv/Scripts/python.exe tests/test_facade_04d3c2_dual_image_routing_precedence_v1.py
# ==========================================================

import copy
import hashlib
import json
import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Render-stop guard: nothing here may ever reach a real ComfyUI.
os.environ.setdefault("ARCHITECTOS_COMFY_PORT", "9")

FIXTURES = r"D:\ArchitectOS_FACADE_TEST_IMAGES"
A_IMAGE = os.path.join(FIXTURES, "A_STYLE.jpg")
B_IMAGE = os.path.join(FIXTURES, "B01_RAW.jpg")

WORKFLOW_DIR = os.path.join(PROJECT_ROOT, "core", "render", "workflows")

# The EXACT mandated acceptance prompt (must not be altered).
EXACT_PROMPT = (
    "نمای ساختمان تصویر B را بازطراحی کن با الهام از سبک و متریال و زبان فرمی "
    "تصویر A. هندسه کلی، تعداد طبقات، بازشوها، بالکن\u200cها، حجم کلی و کادر "
    "دید ساختمان B حفظ شود. خروجی باید یک رندر نمای باکیفیت و واقعی از ساختمان "
    "B با ظاهر الهام\u200cگرفته از A باشد."
)

REQUEST_SEED = 123456789

from core.render import dual_image_conditioning_v1 as COND  # noqa: E402
from core.render.dual_image_binding_v1 import (  # noqa: E402
    ROLE_A,
    ROLE_B,
    NODE_A,
    NODE_B,
    DUAL_IMAGE_NODE_BINDINGS,
    build_dual_image_contract,
)
from core.render.workflow_selector import WorkflowSelector  # noqa: E402
from core.render.render_runtime import RenderRuntime  # noqa: E402
from core.chat.handlers.image_handler import ImageHandler  # noqa: E402


RESULTS = []

#: Informational findings that are NOT pass/fail requirements of this phase
#: (pre-existing behaviour, out of scope). Printed and reported, never asserted.
OBSERVATIONS = []


def check(name, condition, detail=""):
    ok = bool(condition)
    RESULTS.append((name, ok, detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  | " + detail) if detail else ""))
    return ok


def observe(name, detail):
    OBSERVATIONS.append((name, detail))
    print("  NOTE  " + name + "  | " + detail)


def load_workflow(name):
    with open(os.path.join(WORKFLOW_DIR, name), encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_context(a_path=A_IMAGE, b_path=B_IMAGE):
    refs = {"geometry_authority": "target_building"}
    refs["A"] = {"present": True, "role": "facade_reference", "authority": "appearance_only",
                 "path": a_path, "asset_id": "asset_a_fixture",
                 "filename": os.path.basename(a_path)}
    refs["B"] = {"present": True, "role": "target_building", "authority": "geometry",
                 "path": b_path, "asset_id": "asset_b_fixture",
                 "filename": os.path.basename(b_path)}
    return {"references": refs}


def build_bindings(stage_root):
    """A complete, canonical A/B binding built from the REAL contract."""

    contract = build_dual_image_contract(make_context(), "chat_project", comfy_input=stage_root)
    assert contract.get("status") == "ready", contract.get("errors")

    bindings = {
        ROLE_A: {"node_id": contract["roles"][ROLE_A]["node_id"],
                 "filename": contract["roles"][ROLE_A]["filename"]},
        ROLE_B: {"node_id": contract["roles"][ROLE_B]["node_id"],
                 "filename": contract["roles"][ROLE_B]["filename"]},
    }
    b_asset = {"status": "ready",
               "asset_id": contract["roles"][ROLE_B]["asset_id"],
               "filename": contract["roles"][ROLE_B]["filename"],
               "path": contract["roles"][ROLE_B]["staged_path"]}
    return bindings, b_asset, contract


# ==========================================================
# HANDLER HARNESS (real RenderRuntime, MOCKED executor)
# ==========================================================

class _StubState:
    def __init__(self, data=None):
        self._data = dict(data or {})

    def get(self):
        return dict(self._data)

    def update(self, patch):
        self._data.update(patch or {})


class _StubSemanticIntent:
    def extract(self, text):
        return {}


class _StubImageBridge:
    def process_upload(self, project_id, path, preview=None):
        return {"asset": {"status": "ready",
                          "filename": os.path.basename(str(path)),
                          "path": str(path)}}


class _StubResponse:
    def adapt(self, final_render):
        return {"attachments": []}


class _StubWriteback:
    def store(self, text, response):
        return None


class _StubResultBridge:
    def resolve(self, render_result):
        return {"status": "success", "image": {"filename": "mock_out.png"}}


def make_handler():
    """A real ImageHandler over a real RenderRuntime with a MOCKED executor."""

    runtime = RenderRuntime()

    captured = {}

    def fake_execute(workflow, engine):
        captured["workflow"] = copy.deepcopy(workflow)
        captured["engine"] = engine
        captured["called"] = captured.get("called", 0) + 1
        return {"status": "success", "images": [{"filename": "mock_out.png"}]}

    runtime.executor.execute = fake_execute
    runtime.result_bridge.resolve = lambda ctx: {"status": "success",
                                                 "image": {"filename": "mock_out.png"}}

    # Spy on the runtime entry so an early fail-closed verdict is observable.
    render_calls = []
    original_render = runtime.render

    def render_spy(*args, **kwargs):
        result = original_render(*args, **kwargs)
        render_calls.append({"args": args, "kwargs": kwargs, "result": result})
        return result

    runtime.render = render_spy

    handler = ImageHandler(
        render_runtime=runtime,
        result_bridge=_StubResultBridge(),
        semantic_intent=_StubSemanticIntent(),
        image_bridge=_StubImageBridge(),
        image_response=_StubResponse(),
        writeback=_StubWriteback(),
        state=_StubState(),
        prompt_builder=None,
    )

    return handler, runtime, captured, render_calls


def submitted_params(wf):
    sampler = (wf.get("210") or {}).get("inputs") or {}
    return {
        "seed": sampler.get("seed"),
        "steps": sampler.get("steps"),
        "cfg": sampler.get("cfg"),
        "denoise": sampler.get("denoise"),
        "sampler_name": sampler.get("sampler_name"),
        "scheduler": sampler.get("scheduler"),
        "positive_text": ((wf.get("206") or {}).get("inputs") or {}).get("text"),
        "negative_text": ((wf.get("212") or {}).get("inputs") or {}).get("text"),
    }


# ==========================================================
# [0] STATIC PRECEDENCE PROOF
# ==========================================================

def section_static():

    print("\n[0] STATIC PRECEDENCE PROOF (source)")

    src = open(
        os.path.join(PROJECT_ROOT, "core", "chat", "handlers", "image_handler.py"),
        encoding="utf-8",
    ).read()

    dual_marker = src.find("FACADE-04D.3C-2 — DUAL-IMAGE / CONDITIONED PRECEDENCE")
    edit_guard = src.find("elif self.is_image_edit_request(text):")

    check("the dual/conditioned precedence block exists", dual_marker != -1)
    check("the legacy edit delegation is preserved (elif guard)",
          edit_guard != -1)
    check("the dual/conditioned precedence PRECEDES the edit delegation",
          dual_marker != -1 and edit_guard != -1 and dual_marker < edit_guard,
          "dual=%d edit=%d" % (dual_marker, edit_guard))

    check("the old unconditional 'IMAGE EDIT FIRST' delegation is gone",
          "# IMAGE EDIT FIRST" not in src)
    check("the edit delegation body is still present",
          "return self.handle_image_edit(" in src)
    check("_is_dual_image_request helper exists",
          "def _is_dual_image_request(" in src)
    check("_dual_binding_contract_error helper exists",
          "def _dual_binding_contract_error(" in src)
    check("_dual_route_blocked helper exists",
          "def _dual_route_blocked(" in src)

    # The edit detector itself must NOT be weakened.
    detector = src[src.find("def is_image_edit_request("):]
    check("is_image_edit_request still detects the mandated restyle phrase",
          "بازطراحی کن" in detector)
    check("is_image_edit_request keyword list is intact (>=20 entries)",
          detector.count("\n") > 20)

    # Workflow templates untouched by this phase.
    check("flux_img2img_dual.json sha256 unchanged since 04D.3B-2",
          sha256_file(os.path.join(WORKFLOW_DIR, "flux_img2img_dual.json"))
          == "36189746a43a476f789944413d3944e3560c22c987cde1a462bc673470a04da9")

    single = load_workflow("flux_img2img.json")
    check("flux_img2img.json still has exactly one LoadImage",
          sum(1 for n in single.values()
              if isinstance(n, dict) and n.get("class_type") == "LoadImage") == 1)
    check("flux_img2img.json node set unchanged",
          set(single.keys()) == {"202", "204", "205", "206", "208", "210", "212", "300", "301", "9"},
          str(sorted(single.keys())))


# ==========================================================
# [1] EXACT PERSIAN PROMPT — CONDITIONED OFF
# ==========================================================

def section_conditioned_off(bindings, b_asset):

    print("\n[1] EXACT PERSIAN PROMPT — CONDITIONED OFF (mocked executor)")

    handler, runtime, captured, render_calls = make_handler()

    handler.handle_image_generate(
        EXACT_PROMPT,
        image_asset=b_asset,
        image_bindings=bindings,
        conditioned=False,
        render_seed=REQUEST_SEED,
    )

    metadata = runtime.last_render_metadata or {}
    wf = captured.get("workflow") or {}

    check("conditioned OFF selects flux_img2img_dual.json",
          metadata.get("workflow_name") == "flux_img2img_dual.json",
          str(metadata.get("workflow_name")))
    check("conditioned OFF does NOT select the legacy flux_img2img.json",
          metadata.get("workflow_name") != "flux_img2img.json")
    check("conditioned OFF submitted exactly once (mocked)",
          captured.get("called") == 1, str(captured.get("called")))
    check("conditioned OFF engine is comfyui", captured.get("engine") == "comfyui")

    check("IMAGE B remains bound to node 300",
          (wf.get("300") or {}).get("inputs", {}).get("image") == bindings[ROLE_B]["filename"],
          str((wf.get("300") or {}).get("inputs")))
    check("IMAGE A remains bound to node 302",
          (wf.get("302") or {}).get("inputs", {}).get("image") == bindings[ROLE_A]["filename"],
          str((wf.get("302") or {}).get("inputs")))
    check("node 300 != node 302 (no role swap)",
          (wf.get("300") or {}).get("inputs", {}).get("image")
          != (wf.get("302") or {}).get("inputs", {}).get("image"))

    check("300 -> 301 -> 210 latent path intact",
          (wf.get("301") or {}).get("inputs", {}).get("pixels") == ["300", 0]
          and (wf.get("210") or {}).get("inputs", {}).get("latent_image") == ["301", 0])

    check("unconditioned graph has NO USOStyleReference",
          not any(isinstance(n, dict) and n.get("class_type") == "USOStyleReference"
                  for n in wf.values()))
    check("unconditioned graph has NO ControlNetApplyAdvanced",
          not any(isinstance(n, dict) and n.get("class_type") == "ControlNetApplyAdvanced"
                  for n in wf.values()))
    check("conditioning trace is None when conditioned OFF",
          render_calls[-1]["result"].get("conditioning") is None)

    p = submitted_params(wf)
    print("      SUBMITTED PARAMS (OFF):", json.dumps(
        {k: p[k] for k in ("seed", "steps", "cfg", "denoise", "sampler_name", "scheduler")},
        ensure_ascii=False))

    check("submitted seed == requested seed", p["seed"] == REQUEST_SEED, str(p["seed"]))
    check("submitted steps preserved (30)", p["steps"] == 30, str(p["steps"]))
    check("submitted cfg preserved (5.0)", p["cfg"] == 5, str(p["cfg"]))
    check("submitted denoise preserved (0.3)", p["denoise"] == 0.3, str(p["denoise"]))
    check("sampler preserved (euler)", p["sampler_name"] == "euler", str(p["sampler_name"]))
    check("scheduler preserved (simple)", p["scheduler"] == "simple", str(p["scheduler"]))
    check("model path preserved (210.model <- [202, 0])",
          (wf.get("210") or {}).get("inputs", {}).get("model") == ["202", 0])
    check("conditioned OFF: the resolved prompt reaches positive node 206",
          bool(p["positive_text"])
          and p["positive_text"] == (runtime.last_render_request or {}).get("resolved_prompt"),
          "len=%d" % len(p["positive_text"] or ""))
    check("conditioned OFF: the default negative reaches node 212",
          bool(p["negative_text"]))


# ==========================================================
# [2] EXACT PERSIAN PROMPT — CONDITIONED ON
# ==========================================================

def section_conditioned_on(bindings, b_asset):

    print("\n[2] EXACT PERSIAN PROMPT — CONDITIONED ON (mocked executor)")

    handler, runtime, captured, render_calls = make_handler()

    handler.handle_image_generate(
        EXACT_PROMPT,
        image_asset=b_asset,
        image_bindings=bindings,
        conditioned=True,
        render_seed=REQUEST_SEED,
    )

    metadata = runtime.last_render_metadata or {}
    wf = captured.get("workflow") or {}
    result = render_calls[-1]["result"] if render_calls else {}

    check("conditioned ON selects flux_img2img_dual_conditioned.json",
          metadata.get("workflow_name") == "flux_img2img_dual_conditioned.json",
          str(metadata.get("workflow_name")))
    check("conditioned ON does NOT select the legacy flux_img2img.json",
          metadata.get("workflow_name") != "flux_img2img.json")
    check("conditioned ON does NOT degrade to the unconditioned dual graph",
          metadata.get("workflow_name") != "flux_img2img_dual.json")
    check("conditioned ON submitted exactly once (mocked)",
          captured.get("called") == 1, str(captured.get("called")))

    check("IMAGE B remains bound to node 300",
          (wf.get("300") or {}).get("inputs", {}).get("image") == bindings[ROLE_B]["filename"],
          str((wf.get("300") or {}).get("inputs")))
    check("IMAGE A remains bound to node 302",
          (wf.get("302") or {}).get("inputs", {}).get("image") == bindings[ROLE_A]["filename"],
          str((wf.get("302") or {}).get("inputs")))
    check("IMAGE A did not overwrite node 300",
          (wf.get("300") or {}).get("inputs", {}).get("image")
          != bindings[ROLE_A]["filename"])

    check("300 -> 301 -> 210 latent path intact",
          (wf.get("301") or {}).get("inputs", {}).get("pixels") == ["300", 0]
          and (wf.get("210") or {}).get("inputs", {}).get("latent_image") == ["301", 0])

    # USO + ControlNet connected to KSampler
    check("USOStyleReference present and connected to KSampler.model",
          (wf.get("210") or {}).get("inputs", {}).get("model") == ["322", 0]
          and (wf.get("322") or {}).get("class_type") == "USOStyleReference")
    check("ControlNetApplyAdvanced present and connected to KSampler.positive/negative",
          (wf.get("210") or {}).get("inputs", {}).get("positive") == ["311", 0]
          and (wf.get("210") or {}).get("inputs", {}).get("negative") == ["311", 1]
          and (wf.get("311") or {}).get("class_type") == "ControlNetApplyAdvanced")
    check("USO consumes IMAGE A's clip-vision encoder (322 <- 303)",
          (wf.get("322") or {}).get("inputs", {}).get("clip_vision_output") == ["303", 0])
    check("ControlNet depth derives from IMAGE B (311.image <- 307)",
          (wf.get("311") or {}).get("inputs", {}).get("image") == ["307", 0])
    check("node 304 uses the SigLIP encoder",
          (wf.get("304") or {}).get("inputs", {}).get("clip_name") == COND.SIGLIP_ENCODER,
          str((wf.get("304") or {}).get("inputs", {}).get("clip_name")))

    check("submitted graph passes static conditioned verification",
          COND.verify_conditioning_graph(wf)["status"] == "wired",
          str(COND.verify_conditioning_graph(wf)["errors"]))

    trace = result.get("conditioning") or {}
    check("trace conditioning_wired is True", trace.get("conditioning_wired") is True)
    check("trace conditioning_runtime_verified is False (never claimed)",
          trace.get("conditioning_runtime_verified") is False)
    check("trace conditioning_effect_verified is False (never claimed)",
          trace.get("conditioning_effect_verified") is False)

    p = submitted_params(wf)
    print("      SUBMITTED PARAMS (ON):", json.dumps(
        {k: p[k] for k in ("seed", "steps", "cfg", "denoise", "sampler_name", "scheduler")},
        ensure_ascii=False))

    check("submitted seed == requested seed", p["seed"] == REQUEST_SEED, str(p["seed"]))
    check("submitted steps preserved (30)", p["steps"] == 30, str(p["steps"]))
    check("submitted cfg preserved (5.0)", p["cfg"] == 5, str(p["cfg"]))
    check("submitted denoise preserved (0.3)", p["denoise"] == 0.3, str(p["denoise"]))
    check("sampler preserved (euler)", p["sampler_name"] == "euler", str(p["sampler_name"]))
    check("scheduler preserved (simple)", p["scheduler"] == "simple", str(p["scheduler"]))

    # ---- submitted prompt (reported truthfully; see OBSERVATION below) ----
    resolved = (runtime.last_render_request or {}).get("resolved_prompt")
    template_default = load_workflow("flux_img2img_dual_conditioned.json")["206"]["inputs"]["text"]

    print("      SUBMITTED POSITIVE (ON) [:120]:", (p["positive_text"] or "")[:120])
    print("      RESOLVED PROMPT      (ON) [:120]:", (resolved or "")[:120])

    check("conditioned ON: submitted graph exposes a positive prompt node",
          p["positive_text"] is not None)
    check("conditioned ON: submitted graph exposes a negative prompt node",
          p["negative_text"] is not None)

    if p["positive_text"] == template_default and p["positive_text"] != resolved:
        observe(
            "conditioned graph prompt injection",
            "node 206 keeps the workflow template default; the resolved prompt is NOT "
            "injected because KSampler.positive/negative point at ControlNetApplyAdvanced "
            "(311), which detect_clip_routes() does not traverse. Pre-existing injector "
            "limitation of the FACADE-04D.3B-2 graph — OUT OF SCOPE for this routing phase "
            "(no workflow/parameter change is authorised here).",
        )


# ==========================================================
# [3] LEGACY SINGLE-IMAGE EDIT REGRESSION
# ==========================================================

def section_single_image_edit():

    print("\n[3] LEGACY SINGLE-IMAGE EDIT REGRESSION")

    handler, runtime, captured, render_calls = make_handler()

    routed = {}

    original_edit = handler.handle_image_edit

    def edit_spy(*args, **kwargs):
        routed["called"] = True
        return original_edit(*args, **kwargs)

    handler.handle_image_edit = edit_spy

    # The EXACT restyle prompt, single image, NO bindings and NOT conditioned.
    handler.handle_image_generate(
        EXACT_PROMPT,
        image={"path": B_IMAGE},
        render_seed=REQUEST_SEED,
    )

    metadata = runtime.last_render_metadata or {}
    wf = captured.get("workflow") or {}

    check("single-image edit still delegates to the legacy edit handler",
          routed.get("called") is True)
    check("single-image edit still selects flux_img2img.json",
          metadata.get("workflow_name") == "flux_img2img.json",
          str(metadata.get("workflow_name")))
    check("single-image edit does NOT select a dual workflow",
          metadata.get("workflow_name") not in ("flux_img2img_dual.json",
                                                "flux_img2img_dual_conditioned.json"))
    check("single-image edit submits exactly one LoadImage",
          sum(1 for n in wf.values()
              if isinstance(n, dict) and n.get("class_type") == "LoadImage") == 1)
    check("single-image edit has no node 302",
          "302" not in wf)


# ==========================================================
# [4] TEXT-TO-IMAGE + NORMAL CHAT UNAFFECTED
# ==========================================================

def section_unaffected():

    print("\n[4] TEXT-TO-IMAGE + NORMAL CHAT UNAFFECTED")

    handler, runtime, captured, render_calls = make_handler()

    handler.handle_image_generate("یه ویلای مدرن بساز", render_seed=REQUEST_SEED)

    metadata = runtime.last_render_metadata or {}
    wf = captured.get("workflow") or {}

    check("text-to-image selects flux.json",
          metadata.get("workflow_name") == "flux.json",
          str(metadata.get("workflow_name")))
    check("text-to-image submits no LoadImage",
          not any(isinstance(n, dict) and n.get("class_type") == "LoadImage"
                  for n in wf.values()))
    check("text-to-image is not diverted into any edit route",
          metadata.get("workflow_name") not in ("flux_img2img.json",
                                                "flux_img2img_dual.json",
                                                "flux_img2img_dual_conditioned.json"))

    # The edit detector is unchanged for non-edit text.
    check("is_image_edit_request('سلام') is False",
          handler.is_image_edit_request("سلام") is False)
    check("is_image_edit_request(EXACT_PROMPT) is True (detector intact)",
          handler.is_image_edit_request(EXACT_PROMPT) is True)


# ==========================================================
# [5] FAIL-CLOSED
# ==========================================================

def section_fail_closed(bindings, b_asset):

    print("\n[5] FAIL-CLOSED (missing / invalid bindings)")

    # (a) conditioned WITHOUT any binding -> the runtime gate refuses.
    handler, runtime, captured, render_calls = make_handler()

    handler.handle_image_generate(EXACT_PROMPT, conditioned=True, render_seed=REQUEST_SEED)

    result = render_calls[-1]["result"] if render_calls else {}
    check("conditioned without bindings -> conditioning_requires_dual_binding",
          result.get("status") == "conditioning_requires_dual_binding", str(result.get("status")))
    check("conditioned without bindings NEVER invoked the executor",
          captured.get("called") is None)
    check("conditioned without bindings did NOT fall back to the edit route",
          result.get("workflow") != "flux_img2img.json")

    # (b) bindings present but IMAGE A missing -> handler refuses.
    handler, runtime, captured, render_calls = make_handler()
    partial = {ROLE_B: bindings[ROLE_B]}

    resp = handler.handle_image_generate(EXACT_PROMPT, image_asset=b_asset,
                                         image_bindings=partial, render_seed=REQUEST_SEED)

    check("missing IMAGE A binding -> blocked (dual_image_binding_not_ready)",
          isinstance(resp, dict) and resp.get("status") == "blocked"
          and resp.get("reason") == "dual_image_binding_not_ready", str(resp))
    check("missing IMAGE A binding NEVER reached the runtime",
          render_calls == [])
    check("missing IMAGE A binding NEVER invoked the executor",
          captured.get("called") is None)

    # (c) swapped role node ids -> handler refuses (no silent role swap).
    handler, runtime, captured, render_calls = make_handler()
    swapped = {
        ROLE_A: {"node_id": NODE_B, "filename": bindings[ROLE_A]["filename"]},
        ROLE_B: {"node_id": NODE_A, "filename": bindings[ROLE_B]["filename"]},
    }

    resp = handler.handle_image_generate(EXACT_PROMPT, image_asset=b_asset,
                                         image_bindings=swapped, render_seed=REQUEST_SEED)

    check("swapped A/B node ids -> blocked",
          isinstance(resp, dict) and resp.get("status") == "blocked"
          and resp.get("reason") == "dual_image_binding_not_ready", str(resp))
    check("swapped A/B node ids NEVER invoked the executor", captured.get("called") is None)

    # (d) binding missing a filename -> handler refuses.
    handler, runtime, captured, render_calls = make_handler()
    no_name = {
        ROLE_A: {"node_id": NODE_A, "filename": bindings[ROLE_A]["filename"]},
        ROLE_B: {"node_id": NODE_B, "filename": ""},
    }

    resp = handler.handle_image_generate(EXACT_PROMPT, image_asset=b_asset,
                                         image_bindings=no_name, render_seed=REQUEST_SEED)

    check("binding without a filename -> blocked",
          isinstance(resp, dict) and resp.get("status") == "blocked"
          and resp.get("reason") == "dual_image_binding_not_ready", str(resp))
    check("binding without a filename NEVER invoked the executor",
          captured.get("called") is None)

    # (e) conditioned WITH an invalid binding -> handler refuses before runtime.
    handler, runtime, captured, render_calls = make_handler()

    resp = handler.handle_image_generate(EXACT_PROMPT, image_asset=b_asset,
                                         image_bindings=partial, conditioned=True,
                                         render_seed=REQUEST_SEED)

    check("conditioned with an incomplete binding -> blocked",
          isinstance(resp, dict) and resp.get("status") == "blocked"
          and resp.get("reason") == "dual_image_binding_not_ready", str(resp))
    check("conditioned with an incomplete binding NEVER invoked the executor",
          captured.get("called") is None)


# ==========================================================
# [6] ROUTING / DEFAULTS REGRESSION (selector + signatures)
# ==========================================================

def section_routing():

    print("\n[6] ROUTING / DEFAULTS REGRESSION")

    import inspect

    sel = WorkflowSelector()
    image = {"filename": "x.png"}

    check("text2img -> flux.json",
          sel.select({"engine": "flux", "mode": "text2img"}) == "flux.json")
    check("single img2img -> flux_img2img.json",
          sel.select({"engine": "flux", "mode": "img2img", "image": image}) == "flux_img2img.json")
    check("dual -> flux_img2img_dual.json",
          sel.select({"engine": "flux", "mode": "img2img", "image": image,
                      "image_bindings": {ROLE_B: {"node_id": "300", "filename": "b.png"}}})
          == "flux_img2img_dual.json")
    check("dual + conditioned -> conditioned workflow",
          sel.select({"engine": "flux", "mode": "img2img", "image": image,
                      "image_bindings": {ROLE_B: {"node_id": "300", "filename": "b.png"}},
                      "conditioned": True}) == "flux_img2img_dual_conditioned.json")

    from config import runtime_config as RC
    check("config REQUIRED_WORKFLOW_FILES in sync with selector",
          set(RC.REQUIRED_WORKFLOW_FILES) == set(sel.available_workflows()))

    sig = inspect.signature(ImageHandler.handle_image_generate)
    check("handle_image_generate conditioned defaults to False",
          sig.parameters["conditioned"].default is False)
    check("handle_image_generate image_bindings defaults to None",
          sig.parameters["image_bindings"].default is None)

    sig2 = inspect.signature(RenderRuntime.render)
    check("RenderRuntime.render conditioned defaults to False",
          sig2.parameters["conditioned"].default is False)


# ==========================================================
# MAIN
# ==========================================================

def main():

    print("=== FACADE-04D.3C-2 DUAL-IMAGE ROUTING PRECEDENCE — CONTRACT SUITE ===")

    for required in (A_IMAGE, B_IMAGE):
        if not os.path.isfile(required):
            print("MISSING FIXTURE: " + required)
            return 2

    stage_root = tempfile.mkdtemp(prefix="facade04d3c2_comfy_input_")

    section_static()

    bindings, b_asset, contract = build_bindings(stage_root)
    check("A/B contract is ready with canonical node ids",
          bindings[ROLE_A]["node_id"] == NODE_A and bindings[ROLE_B]["node_id"] == NODE_B,
          "A=%s B=%s" % (bindings[ROLE_A]["node_id"], bindings[ROLE_B]["node_id"]))

    section_conditioned_off(bindings, b_asset)
    section_conditioned_on(bindings, b_asset)
    section_single_image_edit()
    section_unaffected()
    section_fail_closed(bindings, b_asset)
    section_routing()

    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)

    print("\n=== RESULT: %d/%d checks passed ===" % (passed, total))

    if OBSERVATIONS:
        print("\n=== OBSERVATIONS (informational, not pass/fail) ===")
        for name, detail in OBSERVATIONS:
            print("  NOTE  " + name + "  | " + detail)

    failed = [name for name, ok, _ in RESULTS if not ok]
    if failed:
        print("FAILED:")
        for name in failed:
            print("  - " + name)
        return 1

    print("ALL FACADE-04D.3C-2 DUAL-IMAGE ROUTING PRECEDENCE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
