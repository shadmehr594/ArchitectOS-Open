# -*- coding: utf-8 -*-
# ==========================================================
# FACADE-04D.3B-2 — CONDITIONED DUAL-IMAGE WORKFLOW (CONTRACT SUITE)
#
# Scope: static graph verification, installed-ComfyUI node/input verification,
# role separation, preservation of the accepted workflows, and MOCKED render
# submissions only.
#
#   * NO real ComfyUI job, NO inference, NO GPU load, NO image generation.
#   * The executor is always replaced by a recorder.
#   * Run DIRECTLY (script-style; a pytest "N passed" line is not evidence):
#       .venv/Scripts/python.exe tests/test_facade_04d3b2_conditioned_workflow_v1.py
# ==========================================================

import copy
import hashlib
import json
import os
import re
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

COMFY_ROOT = r"C:\ComfyUI-Zluda"

FIXTURES = r"D:\ArchitectOS_FACADE_TEST_IMAGES"
A_IMAGE = os.path.join(FIXTURES, "A_STYLE.jpg")
B_IMAGE = os.path.join(FIXTURES, "B01_RAW.jpg")

WORKFLOW_DIR = os.path.join(PROJECT_ROOT, "core", "render", "workflows")

from core.render import dual_image_conditioning_v1 as COND  # noqa: E402
from core.render.dual_image_binding_v1 import (  # noqa: E402
    ROLE_A,
    ROLE_B,
    build_dual_image_contract,
)
from core.render.workflow_selector import WorkflowSelector  # noqa: E402
from core.render.workflow_loader import WorkflowLoader  # noqa: E402
from core.render.image_workflow_injector import ImageWorkflowInjector  # noqa: E402


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
    contract = build_dual_image_contract(make_context(), "chat_project", comfy_input=stage_root)
    assert contract.get("status") == "ready", contract.get("errors")
    return {
        ROLE_A: {"node_id": COND.NODE_A_LOAD, "filename": contract["roles"][ROLE_A]["filename"]},
        ROLE_B: {"node_id": COND.NODE_B_LOAD, "filename": contract["roles"][ROLE_B]["filename"]},
    }, contract


# ==========================================================
# [0] WORKFLOW FILE FORMAT + PRESERVATION OF ACCEPTED WORKFLOWS
# ==========================================================

def section_preservation():

    print("\n[0] WORKFLOW PRESERVATION + API-PROMPT FORMAT")

    cond = load_workflow(COND.CONDITIONED_WORKFLOW)
    dual = load_workflow(COND.UNCONDITIONED_WORKFLOW)
    single = load_workflow("flux_img2img.json")
    text = load_workflow("flux.json")

    # --- API prompt format, not a UI workflow -----------------------------
    def is_api_prompt(wf):
        if not isinstance(wf, dict) or not wf:
            return False
        for node_id, node in wf.items():
            if not isinstance(node, dict):
                return False
            if not isinstance(node.get("class_type"), str):
                return False
            if not isinstance(node.get("inputs"), dict):
                return False
        return True

    check("conditioned workflow is a valid API prompt (class_type + inputs)",
          is_api_prompt(cond))
    check("conditioned workflow has no UI-only keys (nodes/links/widgets_values)",
          not any(k in cond for k in ("nodes", "links", "widgets_values", "last_node_id")))
    check("conditioned workflow has 21 nodes", len(cond) == 21, "n=%d" % len(cond))

    # --- FACADE-04D.2 workflow must be UNCHANGED in every meaningful way --
    expected_dual_nodes = {"202", "204", "205", "206", "212", "210", "208", "9",
                           "300", "301", "302", "303", "304"}
    check("flux_img2img_dual.json node set unchanged",
          set(dual.keys()) == expected_dual_nodes,
          str(sorted(set(dual.keys()) ^ expected_dual_nodes)))
    check("flux_img2img_dual.json still has 300->301->210 latent path",
          dual["301"]["inputs"]["pixels"] == ["300", 0]
          and dual["210"]["inputs"]["latent_image"] == ["301", 0])
    check("flux_img2img_dual.json still has NO conditioning nodes",
          not ({"305", "306", "307", "310", "311", "320", "321", "322"} & set(dual.keys())))

    cond_strings = json.dumps(dual)
    check("flux_img2img_dual.json contains no USO/ControlNet/depth references",
          not any(s in cond_strings for s in
                  ("uso-flux1", "sigclip", "controlnet-union", "depth_anything", "USOStyleReference")))

    check("flux_img2img_dual.json node 304 still the original CLIP-ViT-H encoder",
          dual["304"]["inputs"]["clip_name"] == COND.INCOMPATIBLE_ENCODER)

    # --- single-image and text-to-image workflows untouched ---------------
    check("flux_img2img.json still single LoadImage node 300",
          single["300"]["class_type"] == "LoadImage"
          and sum(1 for n in single.values()
                  if isinstance(n, dict) and n.get("class_type") == "LoadImage") == 1)
    check("flux_img2img.json has no conditioning nodes",
          not ({"302", "303", "304", "305", "306", "307", "310", "311",
                "320", "321", "322"} & set(single.keys())))
    check("flux.json still has no LoadImage",
          not any(isinstance(n, dict) and n.get("class_type") == "LoadImage"
                  for n in text.values()))
    check("flux.json has no conditioning nodes",
          not ({"300", "301", "302", "303", "304", "305", "306", "307",
                "310", "311", "320", "321", "322"} & set(text.keys())))

    # --- the conditioned graph must not alter the D.2 ids it reuses -------
    for node_id, class_type in (("300", "LoadImage"), ("301", "VAEEncode"),
                                ("302", "LoadImage"), ("210", "KSampler")):
        check("conditioned %s is %s (D.2 id preserved)" % (node_id, class_type),
              cond[node_id]["class_type"] == class_type)

    return cond


# ==========================================================
# [1] STATIC GRAPH VERIFICATION
# ==========================================================

def section_graph(cond):

    print("\n[1] STATIC CONDITIONED-GRAPH VERIFICATION")

    report = COND.verify_conditioning_graph(cond)

    for entry in report["checks"]:
        if not entry["ok"]:
            check(entry["check"], False, entry["detail"])

    check("static graph verification passes with no failures",
          report["status"] == "wired" and not report["errors"],
          "%d checks, errors=%s" % (len(report["checks"]), report["errors"]))
    check("graph verification ran >= 50 assertions", len(report["checks"]) >= 50,
          "n=%d" % len(report["checks"]))

    # Explicit role-separation restatement (brief items 13 and 14)
    geo = COND.upstream_from_input(cond, COND.NODE_CONTROLNET_APPLY, "image")
    check("IMAGE A (302) is NOT in the ControlNet geometry source chain",
          COND.NODE_A_LOAD not in geo, str(sorted(geo)))
    check("IMAGE B (300) IS in the ControlNet geometry source chain",
          COND.NODE_B_LOAD in geo, str(sorted(geo)))

    model_path = COND.upstream_from_input(cond, COND.NODE_SAMPLER, "model")
    check("IMAGE A style encoder (303) IS consumed by the active model path",
          COND.NODE_A_ENCODE in model_path and COND.NODE_USO_STYLE in model_path,
          str(sorted(model_path)))

    latent = COND.upstream_from_input(cond, COND.NODE_SAMPLER, "latent_image")
    check("latent source is IMAGE B only",
          COND.NODE_B_LOAD in latent and COND.NODE_A_LOAD not in latent, str(sorted(latent)))

    return report


# ==========================================================
# [2] NODE CLASSES + INPUTS vs INSTALLED COMFYUI DEFINITIONS
# ==========================================================

SOURCE_FILES = {
    "nodes.py": os.path.join(COMFY_ROOT, "nodes.py"),
    "comfy_extras/nodes_model_patch.py": os.path.join(COMFY_ROOT, "comfy_extras", "nodes_model_patch.py"),
    "comfy_extras/nodes_depth_anything_3.py": os.path.join(COMFY_ROOT, "comfy_extras", "nodes_depth_anything_3.py"),
}


def _class_body(text, class_name):
    lines = text.splitlines()
    start = None
    needle = "class " + class_name
    for i, line in enumerate(lines):
        if line.startswith(needle) and line[len(needle):len(needle) + 1] in ("(", ":", " "):
            start = i
            break
    if start is None:
        return None
    body = [lines[start]]
    for line in lines[start + 1:]:
        if line.startswith("class ") or line.startswith("def "):
            break
        body.append(line)
    return "\n".join(body)


def _declared_inputs(body):
    """Input ids declared inside the node's schema.

    V1 nodes declare a literal ``INPUT_TYPES`` dict -> slice it up to
    ``RETURN_TYPES``. V3 nodes declare ``define_schema`` AND keep nested
    DynamicCombo inputs in class-level constants (e.g. ``_DEPTH_RENDER_INPUTS``),
    so the whole class body is the correct region for them.
    """

    if not body:
        return set()

    if "INPUT_TYPES" in body:
        start = body.index("INPUT_TYPES")
        end = body.index("RETURN_TYPES") if "RETURN_TYPES" in body[start:] else len(body)
        region = body[start:end]
    else:
        region = body

    names = set(re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"\s*:', region))
    names |= set(re.findall(r'Input\(\s*"([A-Za-z_][A-Za-z0-9_]*)"', region))
    return names


def section_installed_nodes(cond):

    print("\n[2] NODE CLASSES + INPUTS vs INSTALLED COMFYUI DEFINITIONS")

    if not os.path.isdir(COMFY_ROOT):
        check("installed ComfyUI available for source verification", False, COMFY_ROOT)
        return

    sources = {}
    for rel, path in SOURCE_FILES.items():
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as handle:
                sources[rel] = handle.read()

    check("installed ComfyUI sources readable", len(sources) == len(SOURCE_FILES),
          str(sorted(sources.keys())))

    # Class name -> the file it must be defined in.
    HOME = {
        "UNETLoader": "nodes.py", "DualCLIPLoader": "nodes.py", "VAELoader": "nodes.py",
        "CLIPTextEncode": "nodes.py", "KSampler": "nodes.py", "VAEDecode": "nodes.py",
        "SaveImage": "nodes.py", "LoadImage": "nodes.py", "VAEEncode": "nodes.py",
        "CLIPVisionLoader": "nodes.py", "CLIPVisionEncode": "nodes.py",
        "LoraLoaderModelOnly": "nodes.py", "ControlNetLoader": "nodes.py",
        "ControlNetApplyAdvanced": "nodes.py",
        "ModelPatchLoader": "comfy_extras/nodes_model_patch.py",
        "USOStyleReference": "comfy_extras/nodes_model_patch.py",
        "LoadDA3Model": "comfy_extras/nodes_depth_anything_3.py",
        "DA3Inference": "comfy_extras/nodes_depth_anything_3.py",
        "DA3Render": "comfy_extras/nodes_depth_anything_3.py",
    }

    bodies = {}
    for class_name, rel in HOME.items():
        text = sources.get(rel)
        body = _class_body(text, class_name) if text else None
        bodies[class_name] = body
        check("%s is defined in installed %s" % (class_name, rel), body is not None)

    # Every input key used by the conditioned graph must be declared.
    unknown = []
    for node_id, node in cond.items():
        class_name = node.get("class_type")
        body = bodies.get(class_name)

        if body is None:
            unknown.append("%s:%s (class not found)" % (node_id, class_name))
            continue

        declared = _declared_inputs(body)

        for key in (node.get("inputs") or {}):
            if key.startswith("_architectos"):
                continue
            # V3 DynamicCombo nested inputs are addressed as "<parent>.<child>".
            probe = key.split(".")[-1]
            if probe not in declared:
                unknown.append("%s %s.%s" % (node_id, class_name, key))

    check("every input key is declared by the installed node definition",
          unknown == [], str(unknown))

    # The specific V3 DynamicCombo parent ids must exist.
    check("DA3Inference declares the 'mode' DynamicCombo",
          "mode" in _declared_inputs(bodies.get("DA3Inference")))
    check("DA3Render declares the 'output' DynamicCombo",
          "output" in _declared_inputs(bodies.get("DA3Render")))
    check("DA3Render 'depth' option declares normalization + apply_sky_clip",
          {"normalization", "apply_sky_clip"}.issubset(
              _declared_inputs(bodies.get("DA3Render"))))

    # USOStyleReference must take exactly the three inputs we wired.
    uso = _declared_inputs(bodies.get("USOStyleReference"))
    check("USOStyleReference declares model/model_patch/clip_vision_output",
          {"model", "model_patch", "clip_vision_output"}.issubset(uso), str(sorted(uso)))

    # ControlNetApplyAdvanced must declare an optional vae.
    cna = bodies.get("ControlNetApplyAdvanced") or ""
    check("ControlNetApplyAdvanced declares an optional vae input",
          '"vae"' in cna and '"optional"' in cna)


# ==========================================================
# [3] ROLE-AWARE BINDING (A -> 302, B -> 300)
# ==========================================================

def section_binding(cond, stage_root):

    print("\n[3] ROLE-AWARE BINDING ON THE CONDITIONED GRAPH")

    bindings, contract = build_bindings(stage_root)

    injected = ImageWorkflowInjector().inject(
        cond,
        "restyle the facade",
        {"filename": bindings[ROLE_B]["filename"]},
        {"denoise": 0.55},
        image_bindings=bindings,
    )

    wf = injected["workflow"]

    check("node 300 receives IMAGE B", wf["300"]["inputs"]["image"] == bindings[ROLE_B]["filename"],
          str(wf["300"]["inputs"]["image"]))
    check("node 302 receives IMAGE A", wf["302"]["inputs"]["image"] == bindings[ROLE_A]["filename"],
          str(wf["302"]["inputs"]["image"]))
    check("IMAGE A did not overwrite node 300",
          wf["300"]["inputs"]["image"] != bindings[ROLE_A]["filename"])
    check("IMAGE B did not reach node 302",
          wf["302"]["inputs"]["image"] != bindings[ROLE_B]["filename"])

    loadimages = {nid: n for nid, n in wf.items()
                  if isinstance(n, dict) and n.get("class_type") == "LoadImage"}
    check("exactly two LoadImage nodes, each with its own role filename",
          {nid: n["inputs"]["image"] for nid, n in loadimages.items()}
          == {"300": bindings[ROLE_B]["filename"], "302": bindings[ROLE_A]["filename"]},
          str({nid: n["inputs"]["image"] for nid, n in loadimages.items()}))

    check("binding did not disturb the geometry wiring",
          wf["306"]["inputs"]["image"] == ["300", 0]
          and wf["311"]["inputs"]["image"] == ["307", 0]
          and wf["210"]["inputs"]["latent_image"] == ["301", 0])
    check("binding did not disturb the style wiring",
          wf["303"]["inputs"]["image"] == ["302", 0]
          and wf["322"]["inputs"]["clip_vision_output"] == ["303", 0])

    # The graph must STILL verify after injection.
    after = COND.verify_conditioning_graph(wf)
    check("graph still verifies after role binding", after["status"] == "wired",
          str(after["errors"]))

    check("source template not mutated by injection",
          cond["300"]["inputs"]["image"] == "input.png")


# ==========================================================
# [4] MOCKED COMFYUI PAYLOAD
# ==========================================================

def _mock_runtime():
    from core.render.render_runtime import RenderRuntime

    runtime = RenderRuntime()
    captured = {}

    def fake_execute(workflow, engine):
        captured["workflow"] = copy.deepcopy(workflow)
        captured["engine"] = engine
        captured["called"] = True
        return {"status": "success", "images": [{"filename": "mock_out.png"}]}

    runtime.executor.execute = fake_execute
    runtime.result_bridge.resolve = lambda ctx: {"status": "success",
                                                 "image": {"filename": "mock_out.png"}}
    return runtime, captured


def _design():
    return {"mode": "img2img",
            "prompt": "restyle the facade with the reference style",
            "architectural_intent": {"style": "modern", "mode": "img2img"},
            "project_state": {}}


def section_mocked_payload(bindings, contract):

    print("\n[4] MOCKED COMFYUI PAYLOAD (conditioned)")

    runtime, captured = _mock_runtime()

    b_asset = {"status": "ready",
               "asset_id": contract["roles"][ROLE_B]["asset_id"],
               "filename": contract["roles"][ROLE_B]["filename"],
               "path": contract["roles"][ROLE_B]["staged_path"]}

    result = runtime.render("chat_project", _design(), "flux", b_asset,
                            image_bindings=bindings, conditioned=True)

    check("runtime selected the CONDITIONED workflow",
          (result.get("request_metadata") or {}).get("workflow_name") == COND.CONDITIONED_WORKFLOW,
          str((result.get("request_metadata") or {}).get("workflow_name")))
    check("executor was invoked exactly once (mocked)", captured.get("called") is True)
    check("executor engine is comfyui", captured.get("engine") == "comfyui")

    wf = captured.get("workflow") or {}

    check("MOCKED node 300 == IMAGE B",
          (wf.get("300") or {}).get("inputs", {}).get("image") == bindings[ROLE_B]["filename"],
          str((wf.get("300") or {}).get("inputs")))
    check("MOCKED node 302 == IMAGE A",
          (wf.get("302") or {}).get("inputs", {}).get("image") == bindings[ROLE_A]["filename"],
          str((wf.get("302") or {}).get("inputs")))
    check("MOCKED 210.model <- [322, 0] (USO-conditioned MODEL)",
          (wf.get("210") or {}).get("inputs", {}).get("model") == ["322", 0])
    check("MOCKED 210.positive <- [311, 0] (ControlNet-conditioned)",
          (wf.get("210") or {}).get("inputs", {}).get("positive") == ["311", 0])
    check("MOCKED 210.negative <- [311, 1] (ControlNet-conditioned)",
          (wf.get("210") or {}).get("inputs", {}).get("negative") == ["311", 1])
    check("MOCKED 210.latent_image <- [301, 0] (IMAGE B img2img path preserved)",
          (wf.get("210") or {}).get("inputs", {}).get("latent_image") == ["301", 0])
    check("MOCKED 311.image <- [307, 0] (depth from IMAGE B)",
          (wf.get("311") or {}).get("inputs", {}).get("image") == ["307", 0])
    check("MOCKED 311.vae <- [205, 0] (FLUX VAE)",
          (wf.get("311") or {}).get("inputs", {}).get("vae") == ["205", 0])
    check("MOCKED 322.clip_vision_output <- [303, 0]",
          (wf.get("322") or {}).get("inputs", {}).get("clip_vision_output") == ["303", 0])
    check("MOCKED 320.model <- [202, 0] (LoRA gets the base MODEL)",
          (wf.get("320") or {}).get("inputs", {}).get("model") == ["202", 0])
    check("MOCKED 304 loads SigLIP, not CLIP-ViT-H",
          (wf.get("304") or {}).get("inputs", {}).get("clip_name") == COND.SIGLIP_ENCODER)

    # Trace semantics
    trace = result.get("conditioning") or {}
    check("trace conditioning_wired is True", trace.get("conditioning_wired") is True)
    check("trace conditioning_runtime_verified is False (never claimed)",
          trace.get("conditioning_runtime_verified") is False)
    check("trace conditioning_effect_verified is False (never claimed)",
          trace.get("conditioning_effect_verified") is False)
    check("trace records the conditioned workflow",
          trace.get("workflow") == COND.CONDITIONED_WORKFLOW)

    # The submitted graph must still be a valid conditioned graph.
    check("submitted payload passes static verification",
          COND.verify_conditioning_graph(wf)["status"] == "wired")


# ==========================================================
# [5] FAIL-CLOSED BEHAVIOUR
# ==========================================================

def section_fail_closed(bindings, stage_root):

    print("\n[5] FAIL-CLOSED BEHAVIOUR (no silent downgrade)")

    # (a) conditioned without a dual-image binding
    runtime, captured = _mock_runtime()
    res = runtime.render("chat_project", _design(), "flux", None, conditioned=True)
    check("conditioned without bindings -> conditioning_requires_dual_binding",
          res.get("status") == "conditioning_requires_dual_binding", str(res.get("status")))
    check("conditioned without bindings NEVER invoked the executor",
          captured.get("called") is None)
    check("conditioned without bindings did not fall back to text2img",
          res.get("status") != "success")

    # (b) missing conditioning model files
    runtime, captured = _mock_runtime()
    empty_root = tempfile.mkdtemp(prefix="facade04d3b2_nomodels_")
    original = COND.model_paths
    COND.model_paths = lambda comfy_root=None: {
        entry["role"]: os.path.join(empty_root, entry["filename"]) for entry in COND.MODEL_SPEC
    }
    try:
        res = runtime.render("chat_project", _design(), "flux",
                             {"status": "ready", "filename": "b.png", "path": "x"},
                             image_bindings=bindings, conditioned=True)
    finally:
        COND.model_paths = original

    check("missing conditioning models -> conditioning_models_missing",
          res.get("status") == "conditioning_models_missing", str(res.get("status")))
    check("missing models NEVER invoked the executor", captured.get("called") is None)
    check("missing models reported per role",
          len((res.get("conditioning") or {}).get("models_missing") or []) == len(COND.MODEL_SPEC),
          str((res.get("conditioning") or {}).get("models_missing")))
    check("missing models trace is not wired",
          (res.get("conditioning") or {}).get("conditioning_wired") is False)

    # (c) invalid graph (executor must never be reached)
    runtime, captured = _mock_runtime()
    broken = load_workflow(COND.CONDITIONED_WORKFLOW)
    broken["304"]["inputs"]["clip_name"] = COND.INCOMPATIBLE_ENCODER  # wrong encoder
    runtime.loader.load = lambda name: {"status": "loaded", "workflow": broken}

    res = runtime.render("chat_project", _design(), "flux",
                         {"status": "ready", "filename": "b.png", "path": "x"},
                         image_bindings=bindings, conditioned=True)

    check("invalid conditioned graph -> conditioning_graph_invalid",
          res.get("status") == "conditioning_graph_invalid", str(res.get("status")))
    check("invalid graph NEVER invoked the executor", captured.get("called") is None)
    check("invalid graph reports the failing check",
          any("CLIP-ViT-H" in e for e in (res.get("conditioning") or {}).get("wiring_errors") or []),
          str((res.get("conditioning") or {}).get("wiring_errors")))

    # (d) IMAGE A swapped into the ControlNet geometry source must be rejected
    broken2 = load_workflow(COND.CONDITIONED_WORKFLOW)
    broken2["306"]["inputs"]["image"] = ["302", 0]  # depth from IMAGE A
    rep = COND.verify_conditioning_graph(broken2)
    check("IMAGE A as the geometry source is rejected",
          rep["status"] == "blocked"
          and any("NEVER traces to IMAGE A" in e or "IMAGE B only" in e for e in rep["errors"]),
          str(rep["errors"]))


# ==========================================================
# [6] PRESERVED ROUTING FOR EXISTING REQUESTS
# ==========================================================

def section_routing(bindings):

    print("\n[6] EXISTING ROUTING PRESERVED")

    sel = WorkflowSelector()
    image = {"filename": "x.png"}

    check("text2img -> flux.json",
          sel.select({"engine": "flux", "mode": "text2img"}) == "flux.json")
    check("single img2img -> flux_img2img.json",
          sel.select({"engine": "flux", "mode": "img2img", "image": image}) == "flux_img2img.json")
    check("wan -> wan_i2v.json",
          sel.select({"engine": "wan", "mode": "i2v", "image": image}) == "wan_i2v.json")
    check("dual (no opt-in) -> flux_img2img_dual.json (FACADE-04D.2)",
          sel.select({"engine": "flux", "mode": "img2img", "image": image,
                      "image_bindings": bindings}) == COND.UNCONDITIONED_WORKFLOW)
    check("dual + conditioned -> conditioned workflow",
          sel.select({"engine": "flux", "mode": "img2img", "image": image,
                      "image_bindings": bindings, "conditioned": True}) == COND.CONDITIONED_WORKFLOW)
    check("conditioned is never implied by dual_image alone",
          sel.select({"engine": "flux", "mode": "img2img", "image": image,
                      "dual_image": True}) == COND.UNCONDITIONED_WORKFLOW)

    from config import runtime_config as RC
    check("config REQUIRED_WORKFLOW_FILES in sync with selector",
          set(RC.REQUIRED_WORKFLOW_FILES) == set(sel.available_workflows()))

    # Default (unconditioned) render must not touch conditioning at all.
    runtime, captured = _mock_runtime()
    res = runtime.render("chat_project", _design(), "flux",
                         {"status": "ready", "filename": "b.png", "path": "x"},
                         image_bindings=bindings)

    check("default dual render still uses flux_img2img_dual.json",
          (res.get("request_metadata") or {}).get("workflow_name") == COND.UNCONDITIONED_WORKFLOW,
          str((res.get("request_metadata") or {}).get("workflow_name")))
    check("default dual render has conditioning = None", res.get("conditioning") is None)
    check("default dual render submits the UNCONDITIONED graph",
          not any(isinstance(n, dict) and n.get("class_type") == "USOStyleReference"
                  for n in (captured.get("workflow") or {}).values()))

    # Single-image and text-to-image still render without conditioning.
    runtime2, captured2 = _mock_runtime()
    res2 = runtime2.render("chat_project", _design(), "flux",
                           {"status": "ready", "filename": "single.png", "path": "x"})
    check("single-image render unchanged",
          (res2.get("request_metadata") or {}).get("workflow_name") == "flux_img2img.json"
          and res2.get("conditioning") is None)

    runtime3, captured3 = _mock_runtime()
    res3 = runtime3.render("chat_project",
                           {"mode": "text2img", "prompt": "a modern house",
                            "architectural_intent": {"style": "modern", "mode": "text2img"},
                            "project_state": {}},
                           "flux")
    check("text-to-image render unchanged",
          (res3.get("request_metadata") or {}).get("workflow_name") == "flux.json"
          and res3.get("conditioning") is None)


# ==========================================================
# MAIN
# ==========================================================

def main():

    print("=== FACADE-04D.3B-2 CONDITIONED WORKFLOW CONTRACT SUITE ===")

    for required in (A_IMAGE, B_IMAGE):
        if not os.path.isfile(required):
            print("MISSING FIXTURE: " + required)
            return 2

    stage_root = tempfile.mkdtemp(prefix="facade04d3b2_comfy_input_")

    cond = section_preservation()
    if not isinstance(cond, dict):
        print("conditioned workflow unreadable")
        return 2

    section_graph(cond)
    section_installed_nodes(cond)

    bindings, contract = build_bindings(stage_root)
    section_binding(cond, stage_root)
    section_mocked_payload(bindings, contract)
    section_fail_closed(bindings, stage_root)
    section_routing(bindings)

    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)

    print("\n=== RESULT: %d/%d checks passed ===" % (passed, total))

    failed = [name for name, ok, _ in RESULTS if not ok]
    if failed:
        print("FAILED:")
        for name in failed:
            print("  - " + name)
        return 1

    print("ALL FACADE-04D.3B-2 CONDITIONED WORKFLOW CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
