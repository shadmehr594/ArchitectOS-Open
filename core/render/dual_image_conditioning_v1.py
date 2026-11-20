# -*- coding: utf-8 -*-
"""FACADE-04D.3B-2 — CONDITIONED DUAL-IMAGE GRAPH CONTRACT (V1).

This module describes and statically verifies the CONDITIONED dual-image graph
(``flux_img2img_dual_conditioned.json``) that wires:

* **IMAGE A** (style reference, appearance only) through the **ByteDance USO**
  style path: ``302 LoadImage -> 303 CLIPVisionEncode <- 304 CLIPVisionLoader``
  and ``321 ModelPatchLoader`` into ``322 USOStyleReference``, whose patched
  MODEL feeds ``210 KSampler.model``.
* **IMAGE B** (target building, geometry authority) both as the img2img latent
  source (``300 -> 301 VAEEncode -> 210.latent_image``, unchanged) and as the
  structural guidance source (``300 -> 306 DA3Inference -> 307 DA3Render ->
  311 ControlNetApplyAdvanced.image``).

WIRING IS NOT QUALITY
---------------------
``verify_conditioning_graph`` proves the graph is *wired* correctly. It proves
nothing about what the models do at runtime. The trace therefore carries three
independent fields:

* ``conditioning_wired``            — static graph wiring verified here.
* ``conditioning_runtime_verified`` — always ``False`` until a real, supervised
  execution succeeds.
* ``conditioning_effect_verified``  — always ``False`` until a supervised
  rendered comparison proves IMAGE A measurably changes the output.

No inference, no GPU load and no ComfyUI job happens in this module.
"""

import os

CONTRACT = "DualImageConditioningV1"
VERSION = "1.0"

#: The dedicated conditioned workflow. The accepted FACADE-04D.2 workflow
#: (``flux_img2img_dual.json``) is NEVER modified or replaced.
CONDITIONED_WORKFLOW = "flux_img2img_dual_conditioned.json"

#: The unconditioned FACADE-04D.2 workflow — the default for dual-image work.
UNCONDITIONED_WORKFLOW = "flux_img2img_dual.json"

# ----------------------------------------------------------
# Node ids (the FACADE-04D.2 ids are preserved verbatim)
# ----------------------------------------------------------
NODE_B_LOAD = "300"          # IMAGE B
NODE_B_ENCODE = "301"
NODE_A_LOAD = "302"          # IMAGE A
NODE_A_ENCODE = "303"        # CLIPVisionEncode of IMAGE A
NODE_A_VISION_LOADER = "304" # CLIPVisionLoader (SigLIP)
NODE_BASE_UNET = "202"
NODE_VAE = "205"
NODE_POS = "206"
NODE_NEG = "212"
NODE_SAMPLER = "210"
NODE_DA3_MODEL = "305"
NODE_DA3_INFER = "306"
NODE_DA3_RENDER = "307"
NODE_CONTROLNET_LOADER = "310"
NODE_CONTROLNET_APPLY = "311"
NODE_USO_LORA = "320"
NODE_USO_PATCH = "321"
NODE_USO_STYLE = "322"

#: Every node id -> required class_type.
REQUIRED_NODES = {
    NODE_BASE_UNET: "UNETLoader",
    NODE_VAE: "VAELoader",
    NODE_POS: "CLIPTextEncode",
    NODE_NEG: "CLIPTextEncode",
    NODE_SAMPLER: "KSampler",
    NODE_B_LOAD: "LoadImage",
    NODE_B_ENCODE: "VAEEncode",
    NODE_A_LOAD: "LoadImage",
    NODE_A_ENCODE: "CLIPVisionEncode",
    NODE_A_VISION_LOADER: "CLIPVisionLoader",
    NODE_DA3_MODEL: "LoadDA3Model",
    NODE_DA3_INFER: "DA3Inference",
    NODE_DA3_RENDER: "DA3Render",
    NODE_CONTROLNET_LOADER: "ControlNetLoader",
    NODE_CONTROLNET_APPLY: "ControlNetApplyAdvanced",
    NODE_USO_LORA: "LoraLoaderModelOnly",
    NODE_USO_PATCH: "ModelPatchLoader",
    NODE_USO_STYLE: "USOStyleReference",
}

#: The encoder USO was trained against. ``clip_vision_h`` (CLIP-ViT-H) is a
#: DIFFERENT encoder family and must never appear in this graph.
SIGLIP_ENCODER = "sigclip_vision_patch14_384.safetensors"
INCOMPATIBLE_ENCODER = "clip_vision_h.safetensors"

#: Exact installed conditioning assets (sizes/hashes verified in FACADE-04D.3B-1).
MODEL_SPEC = (
    {
        "role": "style_lora",
        "folder": "loras",
        "filename": "uso-flux1-dit-lora-v1.safetensors",
        "bytes": 478187816,
        "sha256": "a03fa8430997f1c371c2471b133bdc03433a50564e0a29c096217077b0309e41",
    },
    {
        "role": "style_projector",
        "folder": "model_patches",
        "filename": "uso-flux1-projector-v1.safetensors",
        "bytes": 21548200,
        "sha256": "9a0dfcd6644e3acaf6995625562ab0af1f9cf048bf739c7e5822ee106fb44311",
    },
    {
        "role": "style_encoder",
        "folder": "clip_vision",
        "filename": "sigclip_vision_patch14_384.safetensors",
        "bytes": 856505640,
        "sha256": "1fee501deabac72f0ed17610307d7131e3e9d1e838d0363aa3c2b97a6e03fb33",
    },
    {
        "role": "geometry_controlnet",
        "folder": "controlnet",
        "filename": "flux1-dev-controlnet-union-pro-2.0-fp8.safetensors",
        "bytes": 2140902936,
        "sha256": "393fc2a298b93ffe39f2db3f0d2ce11dfba62d44b7aa3c1dd3380d4a1be04deb",
    },
    {
        "role": "geometry_depth_model",
        "folder": "geometry_estimation",
        "filename": "depth_anything_3_small.safetensors",
        "bytes": 137254980,
        "sha256": "9c0a53d157c5b315d4c82908a43d93eeaa3a9ac3de9d15c2b4242ef46b5508ad",
    },
)

#: Loader node id -> the model asset that node must reference.
MODEL_NODE_BINDING = {
    NODE_USO_LORA: ("lora_name", "style_lora"),
    NODE_USO_PATCH: ("name", "style_projector"),
    NODE_A_VISION_LOADER: ("clip_name", "style_encoder"),
    NODE_CONTROLNET_LOADER: ("control_net_name", "geometry_controlnet"),
    NODE_DA3_MODEL: ("model_name", "geometry_depth_model"),
}


def _model_by_role(role):
    for entry in MODEL_SPEC:
        if entry["role"] == role:
            return entry
    return None


def _link(value):
    """A ``[node_id, slot]`` link, normalised, or ``None``."""

    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
        return (value[0], int(value[1]))
    return None


# ----------------------------------------------------------
# Graph traversal (pure, no ComfyUI dependency)
# ----------------------------------------------------------

def upstream_nodes(workflow, start_nodes):
    """All node ids reachable by following input links backwards."""

    seen = set()
    stack = [str(n) for n in start_nodes]

    while stack:
        node_id = stack.pop()
        node = workflow.get(node_id)

        if not isinstance(node, dict):
            continue

        for value in (node.get("inputs") or {}).values():
            link = _link(value)

            if link is None:
                continue

            if link[0] not in seen:
                seen.add(link[0])
                stack.append(link[0])

    return seen


def upstream_from_input(workflow, node_id, input_name):
    """Node ids reachable from ONE named input of ONE node (exclusive)."""

    node = workflow.get(str(node_id)) or {}
    link = _link((node.get("inputs") or {}).get(input_name))

    if link is None:
        return set()

    return upstream_nodes(workflow, [link[0]]) | {link[0]}


# ----------------------------------------------------------
# Model availability (fail-closed)
# ----------------------------------------------------------

def model_paths(comfy_root=None):
    """Absolute expected path of every conditioning asset."""

    if comfy_root is None:
        from config import runtime_config as RC

        comfy_root = RC.COMFYUI_ROOT

    return {
        entry["role"]: os.path.join(comfy_root, "models", entry["folder"], entry["filename"])
        for entry in MODEL_SPEC
    }


def verify_conditioning_models(comfy_root=None, verify_hash=False):
    """Fail-closed availability check for the five conditioning assets."""

    paths = model_paths(comfy_root)

    present = {}
    missing = []
    wrong_size = []

    for entry in MODEL_SPEC:
        role = entry["role"]
        path = paths[role]

        if not os.path.isfile(path):
            missing.append({"role": role, "path": path})
            present[role] = False
            continue

        size = os.path.getsize(path)

        if size != entry["bytes"]:
            wrong_size.append({"role": role, "path": path,
                               "expected_bytes": entry["bytes"], "bytes": size})
            present[role] = False
            continue

        if verify_hash:
            import hashlib

            digest = hashlib.sha256()

            with open(path, "rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 22), b""):
                    digest.update(chunk)

            if digest.hexdigest() != entry["sha256"]:
                wrong_size.append({"role": role, "path": path,
                                   "expected_bytes": entry["bytes"], "bytes": size,
                                   "hash_mismatch": True})
                present[role] = False
                continue

        present[role] = True

    status = "ready" if not missing and not wrong_size else "blocked"

    return {
        "contract": CONTRACT,
        "status": status,
        "comfy_root": comfy_root,
        "present": present,
        "missing": missing,
        "invalid": wrong_size,
        "hash_verified": bool(verify_hash),
    }


# ----------------------------------------------------------
# Static graph verification
# ----------------------------------------------------------

def verify_conditioning_graph(workflow):
    """Statically verify the conditioned graph. Returns a report dict."""

    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)})
        return bool(ok)

    if not isinstance(workflow, dict):
        return {
            "contract": CONTRACT,
            "status": "blocked",
            "errors": ["invalid_workflow"],
            "checks": checks,
        }

    def node(node_id):
        n = workflow.get(node_id)
        return n if isinstance(n, dict) else {}

    def inputs(node_id):
        return node(node_id).get("inputs") or {}

    # --- node presence and class types -------------------------------------
    for node_id, class_type in REQUIRED_NODES.items():
        actual = node(node_id).get("class_type")
        check("node %s is %s" % (node_id, class_type), actual == class_type,
              "actual=%s" % actual)

    samplers = [nid for nid, n in workflow.items()
                if isinstance(n, dict) and n.get("class_type") == "KSampler"]
    check("exactly one KSampler", samplers == [NODE_SAMPLER], str(samplers))

    # --- IMAGE B img2img latent path (FACADE-04D.2 preserved) --------------
    check("301 VAEEncode.pixels <- [300, 0]", _link(inputs(NODE_B_ENCODE).get("pixels")) == (NODE_B_LOAD, 0),
          str(inputs(NODE_B_ENCODE).get("pixels")))
    check("210 KSampler.latent_image <- [301, 0]", _link(inputs(NODE_SAMPLER).get("latent_image")) == (NODE_B_ENCODE, 0),
          str(inputs(NODE_SAMPLER).get("latent_image")))
    check("301 VAEEncode.vae <- [205, 0]", _link(inputs(NODE_B_ENCODE).get("vae")) == (NODE_VAE, 0),
          str(inputs(NODE_B_ENCODE).get("vae")))

    # --- USO style path ----------------------------------------------------
    check("304 CLIPVisionLoader loads SigLIP",
          inputs(NODE_A_VISION_LOADER).get("clip_name") == SIGLIP_ENCODER,
          str(inputs(NODE_A_VISION_LOADER).get("clip_name")))
    check("303 CLIPVisionEncode.clip_vision <- [304, 0]",
          _link(inputs(NODE_A_ENCODE).get("clip_vision")) == (NODE_A_VISION_LOADER, 0),
          str(inputs(NODE_A_ENCODE).get("clip_vision")))
    check("303 CLIPVisionEncode.image <- [302, 0] (IMAGE A)",
          _link(inputs(NODE_A_ENCODE).get("image")) == (NODE_A_LOAD, 0),
          str(inputs(NODE_A_ENCODE).get("image")))

    check("322 USOStyleReference.clip_vision_output <- [303, 0] (encoder output CONSUMED)",
          _link(inputs(NODE_USO_STYLE).get("clip_vision_output")) == (NODE_A_ENCODE, 0),
          str(inputs(NODE_USO_STYLE).get("clip_vision_output")))
    check("322 USOStyleReference.model_patch <- [321, 0]",
          _link(inputs(NODE_USO_STYLE).get("model_patch")) == (NODE_USO_PATCH, 0),
          str(inputs(NODE_USO_STYLE).get("model_patch")))
    check("322 USOStyleReference.model <- [320, 0] (LoRA-patched MODEL)",
          _link(inputs(NODE_USO_STYLE).get("model")) == (NODE_USO_LORA, 0),
          str(inputs(NODE_USO_STYLE).get("model")))
    check("320 LoraLoaderModelOnly.model <- [202, 0] (the ACTUAL base MODEL)",
          _link(inputs(NODE_USO_LORA).get("model")) == (NODE_BASE_UNET, 0),
          str(inputs(NODE_USO_LORA).get("model")))
    check("210 KSampler.model <- [322, 0] (USO-conditioned MODEL)",
          _link(inputs(NODE_SAMPLER).get("model")) == (NODE_USO_STYLE, 0),
          str(inputs(NODE_SAMPLER).get("model")))

    # --- geometry (depth + ControlNet) path --------------------------------
    check("306 DA3Inference.image <- [300, 0] (IMAGE B)",
          _link(inputs(NODE_DA3_INFER).get("image")) == (NODE_B_LOAD, 0),
          str(inputs(NODE_DA3_INFER).get("image")))
    check("306 DA3Inference.da3_model <- [305, 0]",
          _link(inputs(NODE_DA3_INFER).get("da3_model")) == (NODE_DA3_MODEL, 0),
          str(inputs(NODE_DA3_INFER).get("da3_model")))
    check("307 DA3Render.da3_geometry <- [306, 0]",
          _link(inputs(NODE_DA3_RENDER).get("da3_geometry")) == (NODE_DA3_INFER, 0),
          str(inputs(NODE_DA3_RENDER).get("da3_geometry")))
    check("311 ControlNetApplyAdvanced.image <- [307, 0] (IMAGE B depth)",
          _link(inputs(NODE_CONTROLNET_APPLY).get("image")) == (NODE_DA3_RENDER, 0),
          str(inputs(NODE_CONTROLNET_APPLY).get("image")))
    check("311 ControlNetApplyAdvanced.control_net <- [310, 0]",
          _link(inputs(NODE_CONTROLNET_APPLY).get("control_net")) == (NODE_CONTROLNET_LOADER, 0),
          str(inputs(NODE_CONTROLNET_APPLY).get("control_net")))
    check("311 ControlNetApplyAdvanced.vae <- [205, 0] (REQUIRED for FLUX ControlNet)",
          _link(inputs(NODE_CONTROLNET_APPLY).get("vae")) == (NODE_VAE, 0),
          str(inputs(NODE_CONTROLNET_APPLY).get("vae")))

    # --- conditioning routing ---------------------------------------------
    check("311 positive <- [206, 0]", _link(inputs(NODE_CONTROLNET_APPLY).get("positive")) == (NODE_POS, 0),
          str(inputs(NODE_CONTROLNET_APPLY).get("positive")))
    check("311 negative <- [212, 0]", _link(inputs(NODE_CONTROLNET_APPLY).get("negative")) == (NODE_NEG, 0),
          str(inputs(NODE_CONTROLNET_APPLY).get("negative")))
    check("210 positive <- [311, 0] (conditioned)", _link(inputs(NODE_SAMPLER).get("positive")) == (NODE_CONTROLNET_APPLY, 0),
          str(inputs(NODE_SAMPLER).get("positive")))
    check("210 negative <- [311, 1] (conditioned)", _link(inputs(NODE_SAMPLER).get("negative")) == (NODE_CONTROLNET_APPLY, 1),
          str(inputs(NODE_SAMPLER).get("negative")))

    # --- model filenames must match the installed assets exactly ----------
    for node_id, (input_name, role) in MODEL_NODE_BINDING.items():
        entry = _model_by_role(role)
        actual = inputs(node_id).get(input_name)
        check("%s %s is the installed %s" % (node_id, input_name, role),
              actual == entry["filename"], "actual=%s expected=%s" % (actual, entry["filename"]))

    # --- no incompatible encoder anywhere ---------------------------------
    offenders = []
    for nid, n in workflow.items():
        if not isinstance(n, dict):
            continue
        for key, value in (n.get("inputs") or {}).items():
            if isinstance(value, str) and value == INCOMPATIBLE_ENCODER:
                offenders.append("%s.%s" % (nid, key))
    check("no stale CLIP-ViT-H encoder (%s) in the graph" % INCOMPATIBLE_ENCODER,
          offenders == [], str(offenders))

    # --- ROLE SEPARATION: IMAGE A must never reach the geometry source ----
    geometry_sources = upstream_from_input(workflow, NODE_CONTROLNET_APPLY, "image")
    check("ControlNet image traces to IMAGE B (300)", NODE_B_LOAD in geometry_sources,
          str(sorted(geometry_sources)))
    check("ControlNet image NEVER traces to IMAGE A (302)", NODE_A_LOAD not in geometry_sources,
          str(sorted(geometry_sources)))

    depth_sources = upstream_from_input(workflow, NODE_DA3_INFER, "image")
    check("depth preprocessor reads IMAGE B only",
          NODE_B_LOAD in depth_sources and NODE_A_LOAD not in depth_sources,
          str(sorted(depth_sources)))

    # --- IMAGE A style encoder must be CONSUMED by the active model path --
    model_path = upstream_from_input(workflow, NODE_SAMPLER, "model")
    check("sampler model path reaches USOStyleReference (322)", NODE_USO_STYLE in model_path,
          str(sorted(model_path)))
    check("sampler model path reaches the IMAGE A style encoder (303)", NODE_A_ENCODE in model_path,
          str(sorted(model_path)))
    check("sampler model path reaches the USO projector (321)", NODE_USO_PATCH in model_path,
          str(sorted(model_path)))
    check("sampler model path reaches the base UNET (202)", NODE_BASE_UNET in model_path,
          str(sorted(model_path)))

    # --- IMAGE A must not be the latent source ----------------------------
    latent_sources = upstream_from_input(workflow, NODE_SAMPLER, "latent_image")
    check("latent source traces to IMAGE B (300)", NODE_B_LOAD in latent_sources,
          str(sorted(latent_sources)))
    check("latent source never traces to IMAGE A (302)", NODE_A_LOAD not in latent_sources,
          str(sorted(latent_sources)))

    failed = [c["check"] for c in checks if not c["ok"]]

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "status": "wired" if not failed else "blocked",
        "workflow": CONDITIONED_WORKFLOW,
        "errors": failed,
        "checks": checks,
        "node_count": len(workflow),
        "node_ids": sorted(workflow.keys(), key=lambda s: (len(s), s)),
        "image_a_nodes": [NODE_A_LOAD, NODE_A_ENCODE, NODE_A_VISION_LOADER,
                          NODE_USO_PATCH, NODE_USO_LORA, NODE_USO_STYLE],
        "image_b_nodes": [NODE_B_LOAD, NODE_B_ENCODE, NODE_DA3_MODEL,
                          NODE_DA3_INFER, NODE_DA3_RENDER, NODE_CONTROLNET_LOADER,
                          NODE_CONTROLNET_APPLY],
    }


def conditioning_trace(graph_report=None, model_report=None):
    """The three independent conditioning trace fields.

    ``conditioning_wired`` reflects the STATIC wiring verification only.
    ``conditioning_runtime_verified`` and ``conditioning_effect_verified`` are
    deliberately hard-coded ``False`` in this phase: no execution and no
    comparison has happened, so neither may be claimed.
    """

    wired = bool(graph_report) and graph_report.get("status") == "wired"

    if model_report is not None and model_report.get("status") != "ready":
        wired = False

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "workflow": CONDITIONED_WORKFLOW,
        "conditioning_wired": wired,
        "conditioning_runtime_verified": False,
        "conditioning_effect_verified": False,
        "wiring_errors": list((graph_report or {}).get("errors") or []),
        "model_status": (model_report or {}).get("status"),
        "models_missing": [m["role"] for m in ((model_report or {}).get("missing") or [])],
        "models_invalid": [m["role"] for m in ((model_report or {}).get("invalid") or [])],
        "note": (
            "conditioning_wired proves graph wiring only. It does NOT prove that "
            "the models load, run, or change the rendered output. Those require a "
            "supervised live render (FACADE-04D.3C)."
        ),
    }


# ----------------------------------------------------------
# REFERENCE_TRANSFER_POLICY_V1 — which graph does this turn need?
# ----------------------------------------------------------
#
# The conditioned graph used to be reachable ONLY through an explicit
# `conditioned_render` flag from the UI. A user who simply asked "apply the
# style and materials of this reference to my building" therefore got
# `flux_img2img_dual.json`, whose reference branch is inert (node 303 is not
# consumed) - the request silently did nothing with IMAGE A.
#
# This resolver derives the answer from contracts that already exist:
#
#   * IMAGE ROLES      - both role-bound images must be present (A + B).
#   * IMAGE INTENT     - the turn must be a modification, not an observation.
#   * REFERENCE POLICY - the user must have asked to TAKE something from the
#                        reference (style_only / material_only). A plain
#                        "compare these" is inspiration_only and is excluded.
#   * CAPABILITY       - the five conditioning assets must be present.
#   * EXPLICIT OVERRIDE- a UI choice always wins, including an explicit OFF.
#
# It deliberately does NOT treat every two-image message as style transfer.

#: Reference roles that mean "take appearance from IMAGE A".
TRANSFER_REFERENCE_ROLES = ("style_only", "material_only")

#: Render modes in which a dual-image transfer can legitimately execute.
#: An analysis/observation mode can never select a render graph.
TRANSFER_RENDER_MODES = ("image_to_image", "image_edit", "edit", "auto", None)

#: Comparison language. A turn that asks to COMPARE two images is an
#: analysis request even when it mentions style or materials, so it must not
#: be upgraded to a conditioned render. Bilingual because the product's
#: understanding layer is bilingual.
COMPARISON_MARKERS = (
    "compare", "comparison", "difference", "differences", "versus", " vs ",
    "مقایسه", "تفاوت", "فرق",
)

#: Explicit OFF values a UI may send for `conditioned_render`.
_FALSEY = ("0", "false", "no", "off", "")


def _text_asks_comparison(text):
    lowered = " " + str(text or "").lower() + " "
    return any(marker in lowered for marker in COMPARISON_MARKERS)


def parse_conditioned_flag(value):
    """Tri-state parse of the UI `conditioned_render` field.

    Returns True (explicit ON), False (explicit OFF) or None (not supplied).

    The previous `bool(value)` treatment was wrong for the multipart path:
    the string "0" is truthy, so an explicit OFF from the client would have
    switched conditioning ON.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    if text in _FALSEY:
        return False

    if text in ("1", "true", "yes", "on"):
        return True

    return None


def resolve_conditioning(
    *,
    role_bindings=None,
    reference_policy=None,
    mode=None,
    text="",
    explicit=None,
    capability=None,
    comfy_root=None,
):
    """Decide whether this dual-image turn uses the conditioned graph.

    Returns a deterministic contract. `conditioned` is the only field the
    render path must honour; `source` and `reason` are the truthful account of
    WHY, so the response envelope can report the decision instead of guessing.
    """

    role_bindings = role_bindings if isinstance(role_bindings, dict) else {}
    policy = reference_policy if isinstance(reference_policy, dict) else {}

    roles = {
        str(k).upper(): v
        for k, v in role_bindings.items()
    }

    pair_present = bool(roles.get("A") and roles.get("B"))

    reference_role = policy.get("role") or "none"

    explicit = parse_conditioned_flag(explicit)

    result = {
        "contract": "ReferenceTransferPolicyV1",
        "version": "1.0",
        "conditioned": False,
        "source": "default",
        "reason": None,
        "pair_present": pair_present,
        "reference_role": reference_role,
        "mode": mode,
        "explicit": explicit,
        "capability_status": None,
        "blocked_reason": None,
    }

    def _blocked(reason):
        result["reason"] = reason
        result["blocked_reason"] = reason
        return result

    # ---- 1. explicit UI override wins -------------------------------
    if explicit is True:
        result["source"] = "explicit_ui"
        result["reason"] = "explicit_ui_opt_in"
        result["conditioned"] = True
    elif explicit is False:
        result["source"] = "explicit_ui"
        result["reason"] = "explicit_ui_opt_out"
        result["conditioned"] = False
        return result
    else:
        # ---- 2. derive from the contracts ---------------------------
        if not pair_present:
            return _blocked("role_pair_absent")

        if str(mode).strip().lower() not in [
            str(m).lower() for m in TRANSFER_RENDER_MODES
        ]:
            return _blocked("mode_is_not_a_render_mode")

        if _text_asks_comparison(text):
            return _blocked("comparison_request")

        if reference_role not in TRANSFER_REFERENCE_ROLES:
            return _blocked("no_transfer_role_requested")

        result["source"] = "reference_transfer_intent"
        result["reason"] = "explicit_transfer_of_" + str(reference_role)
        result["conditioned"] = True

    # ---- 3. capability gate (only when we intend to condition) ------
    if result["conditioned"]:

        report = capability

        if report is None:

            try:

                report = verify_conditioning_models(
                    comfy_root=comfy_root
                )

            except Exception as error:  # pragma: no cover - defensive

                report = {
                    "status": "blocked",
                    "missing": [],
                    "invalid": [],
                    "error": repr(error),
                }

        result["capability_status"] = report.get("status")

        if report.get("status") != "ready":

            result["conditioned"] = False
            result["blocked_reason"] = "conditioning_models_unavailable"
            result["reason"] = (
                str(result["reason"])
                + ":blocked_by_capability"
            )

    return result
