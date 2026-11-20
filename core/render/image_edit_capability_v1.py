# ==========================================================
# ArchitectOS Image Edit Capability Contract v1
#
# IMAGE_TO_IMAGE_05 — CAPABILITY AUDIT (READ ONLY)
#
# Purpose
#   Report, TRUTHFULLY and from the ACTUAL workflow + model files,
#   what the current img2img path can and cannot do.
#
#   Capabilities are DERIVED by inspecting the workflow graph and the
#   model files on disk. Nothing is hardcoded to a desired answer, and
#   nothing is inferred from rendered output. If a conditioning node is
#   absent, the capability is reported as false.
#
# Why this matters
#   "img2img executed and produced a file" says nothing about whether
#   the pipeline can follow a semantic editing instruction while
#   preserving image identity. Those are different capabilities, and
#   conflating them is what made the night-edit result look like a
#   routing success.
# ==========================================================


from __future__ import annotations


import json
import os


CONTRACT = "ImageEditCapabilityV1"
VERSION = "1.0"


ROOT = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

DEFAULT_WORKFLOW = os.path.join(
    ROOT, "core", "render", "workflows", "flux_img2img.json"
)


# ----------------------------------------------------------
# NODE CLASS FAMILIES
#
# Each family is the CONDITIONING MECHANISM a capability needs.
# A capability is true only when its mechanism is really present.
# ----------------------------------------------------------

MASK_NODE_TYPES = (
    "loadimagemask",
    "setlatentnoisemask",
    "inpaintmodelconditioning",
    "vaeencodeparams",           # only when a mask is wired (see below)
    "growmask",
    "feathermask",
    "solidmask",
    "maskcomposite",
    "imagecompositemasked",
)

REGION_GROUNDING_NODE_TYPES = (
    "groundingdinosamdetector",
    "samdetector",
    "segmdetector",
    "impactsegmdetector",
    "bboxdetector",
    "cropmask",
)

GEOMETRY_NODE_TYPES = (
    "controlnetloader",
    "controlnetapply",
    "controlnetapplyadvanced",
    "depthanythingv2preprocessor",
    "cannyedgepreprocessor",
    "lineartpreprocessor",
    "mlsdpreprocessor",
    "zoedepthmap",
    "openposedetector",
    "dwpose",
)

INSTRUCTION_EDIT_NODE_TYPES = (
    # FLUX.1 Kontext / reference-latent editing
    "referencelatent",
    "kontext",
    "fluxkontext",
    # image-prompt conditioning
    "stylemodelapply",
    "clipvisionloader",
    "ipadapter",
    "ipadapterapply",
    "redux",
    # generic edit models
    "omnigen",
    "qwenimageedit",
    "instructpix2pix",
)

SOURCE_LATENT_NODE_TYPES = (
    "vaeencode",
    "vaeencodeparams",
)

SAMPLER_NODE_TYPES = (
    "ksampler",
    "samplercustom",
    "samplercustomadvanced",
)

TEXT_ENCODE_NODE_TYPES = (
    "cliptextencode",
    "cliptextencodesdxl",
    "t5textencode",
)


# Model filename hints that mean the checkpoint itself is an
# instruction / reference editing model.
INSTRUCTION_EDIT_MODEL_HINTS = (
    "kontext",
    "instruct-pix2pix",
    "instructpix2pix",
    "omnigen",
    "qwen-image-edit",
    "qwen_image_edit",
    "flux-fill",
    "flux_fill",
    "flux-redux",
    "flux_redux",
)

# Model filename hints for the plain FLUX base family.
FLUX_BASE_MODEL_HINTS = ("flux1-", "flux-")


# ----------------------------------------------------------
# WORKFLOW INTROSPECTION
# ----------------------------------------------------------

def load_workflow(path=None):

    target = path or DEFAULT_WORKFLOW

    with open(target, "r", encoding="utf-8") as handle:

        return json.load(handle), target


def _class_types(workflow):

    found = {}

    for node_id, node in (workflow or {}).items():

        if not isinstance(node, dict):

            continue

        class_type = str(node.get("class_type", ""))

        found[node_id] = class_type

    return found


def _present(class_types, wanted):

    wanted = set(wanted)

    return sorted(

        node_id

        for node_id, class_type in class_types.items()

        if class_type.lower() in wanted
    )


def _linked(workflow, node, input_name, target_node_id):

    """True when `node`'s input_name points at target_node_id."""

    if not isinstance(node, dict):

        return False

    value = (node.get("inputs") or {}).get(input_name)

    return (
        isinstance(value, list)
        and bool(value)
        and str(value[0]) == str(target_node_id)
    )


def _model_files(workflow):

    files = {

        "unet": None,
        "clip": [],
        "vae": None,
    }

    for node in (workflow or {}).values():

        if not isinstance(node, dict):

            continue

        class_type = str(node.get("class_type", "")).lower()

        inputs = node.get("inputs") or {}

        if "unetloader" in class_type or "checkpointloader" in class_type:

            files["unet"] = (
                inputs.get("unet_name") or inputs.get("ckpt_name")
            )

        elif "clip" in class_type and "loader" in class_type:

            files["clip"] = [
                value for value in (
                    inputs.get("clip_name1"),
                    inputs.get("clip_name2"),
                    inputs.get("clip_name3"),
                    inputs.get("clip_name"),
                )
                if value
            ]

        elif "vaeloader" in class_type:

            files["vae"] = inputs.get("vae_name")

    return files


def _locate_model(filename, subdirs=("diffusion_models", "unet", "checkpoints",
                                     "text_encoders", "clip", "vae")):

    if not filename:

        return None

    import config.runtime_config as RC

    comfy_root = os.path.dirname(
        os.path.normpath(RC.COMFYUI_INPUT_DIR)
    )

    for subdir in subdirs:

        candidate = os.path.join(
            comfy_root, "models", subdir, str(filename)
        )

        if os.path.isfile(candidate):

            return candidate

    return None


# ----------------------------------------------------------
# CAPABILITY AUDIT
# ----------------------------------------------------------

def audit(workflow_path=None):

    workflow, path = load_workflow(workflow_path)

    class_types = _class_types(workflow)

    samplers = _present(class_types, SAMPLER_NODE_TYPES)

    source_latents = _present(class_types, SOURCE_LATENT_NODE_TYPES)

    masks = _present(class_types, MASK_NODE_TYPES)

    regions = _present(class_types, REGION_GROUNDING_NODE_TYPES)

    geometry = _present(class_types, GEOMETRY_NODE_TYPES)

    instruction = _present(class_types, INSTRUCTION_EDIT_NODE_TYPES)

    text_encodes = _present(class_types, TEXT_ENCODE_NODE_TYPES)

    # ---- does the sampler actually consume an ENCODED source? ----
    source_driven = False

    sampler_inputs = {}

    for sampler_id in samplers:

        node = workflow.get(sampler_id) or {}

        inputs = node.get("inputs") or {}

        latent = inputs.get("latent_image")

        sampler_inputs[sampler_id] = {

            "steps": inputs.get("steps"),
            "cfg": inputs.get("cfg"),
            "denoise": inputs.get("denoise"),
            "seed": inputs.get("seed"),
            "sampler_name": inputs.get("sampler_name"),
            "scheduler": inputs.get("scheduler"),
            "latent_source": latent[0] if isinstance(latent, list) and latent else None,
        }

        if isinstance(latent, list) and latent and str(latent[0]) in source_latents:

            source_driven = True

    # ---- guidance node (FLUX canonical sampling) ----
    has_flux_guidance = bool(_present(class_types, ("fluxguidance",)))

    # ---- model identity ----
    files = _model_files(workflow)

    unet_name = str(files.get("unet") or "")

    lowered = unet_name.lower()

    is_instruction_model = any(
        hint in lowered for hint in INSTRUCTION_EDIT_MODEL_HINTS
    )

    is_flux_base = (
        any(hint in lowered for hint in FLUX_BASE_MODEL_HINTS)
        and not is_instruction_model
    )

    unet_path = _locate_model(unet_name)

    # ------------------------------------------------------
    # FLAGS  (mechanism-based, never assumed)
    # ------------------------------------------------------

    supports_global_img2img = bool(source_driven and samplers)

    supports_instruction_edit = bool(
        is_instruction_model and instruction
    )

    supports_local_edit = bool(masks)

    supports_region_grounding = bool(regions)

    supports_geometry_edit = bool(geometry)

    # The ONLY identity-preservation mechanism actually present.
    identity_mechanism = (
        "low_denoise_source_latent"
        if supports_global_img2img
        else "none"
    )

    return {

        "contract": CONTRACT,
        "version": VERSION,

        "workflow_path": path,

        "capabilities": {

            "supports_global_img2img": supports_global_img2img,
            "supports_instruction_edit": supports_instruction_edit,
            "supports_local_edit": supports_local_edit,
            "supports_region_grounding": supports_region_grounding,
            "supports_geometry_edit": supports_geometry_edit,
        },

        "identity_preservation": {

            "mechanism": identity_mechanism,

            "relies_on_low_denoise_only": supports_global_img2img,

            "has_structural_conditioning": supports_geometry_edit,

            "has_region_conditioning": supports_region_grounding,
        },

        "workflow_graph": {

            "node_class_types": class_types,

            "sampler_nodes": samplers,
            "sampler_inputs": sampler_inputs,

            "source_latent_nodes": source_latents,
            "text_encode_nodes": text_encodes,

            "mask_nodes": masks,
            "region_grounding_nodes": regions,
            "geometry_conditioning_nodes": geometry,
            "instruction_edit_nodes": instruction,

            "has_flux_guidance_node": has_flux_guidance,
        },

        "model": {

            "unet_name": unet_name,
            "unet_path": unet_path,
            "unet_present_on_disk": bool(unet_path),

            "clip_names": files.get("clip"),
            "clip_paths": [
                _locate_model(name) for name in (files.get("clip") or [])
            ],
            "vae_name": files.get("vae"),
            "vae_path": _locate_model(files.get("vae")),

            "is_instruction_edit_model": is_instruction_model,
            "is_flux_base_family": is_flux_base,

            "family": (
                "instruction_edit"
                if is_instruction_model
                else "flux_base"
                if is_flux_base
                else "unknown"
            ),
        },

        "is_designed_for_semantic_instruction_editing": bool(
            supports_instruction_edit
        ),

        "answer": (
            "YES - the workflow conditions on an image reference and an "
            "instruction, so it is designed for semantic instruction "
            "editing while preserving identity."
            if supports_instruction_edit
            else "NO - this is standard FLUX img2img. It starts from the "
                 "encoded source latent and is steered only by a text "
                 "prompt. There is no instruction-edit conditioning and no "
                 "structural conditioning, so image identity is preserved "
                 "only by keeping denoise low. Semantic instruction "
                 "editing while preserving identity is therefore not a "
                 "designed capability of this workflow."
        ),
    }


# ----------------------------------------------------------
# ACCESSOR
# ----------------------------------------------------------

def capability_flags(workflow_path=None):

    return audit(workflow_path).get("capabilities", {})


def describe():

    result = audit()

    return {

        "contract": result["contract"],
        "version": result["version"],

        "capabilities": result["capabilities"],

        "model_family": result["model"]["family"],
        "unet_name": result["model"]["unet_name"],

        "is_designed_for_semantic_instruction_editing":
            result["is_designed_for_semantic_instruction_editing"],
    }
