# -*- coding: utf-8 -*-
"""FACADE-04D.2 — ROLE-AWARE DUAL-IMAGE RENDER BINDING V1.

Transport and binding ONLY. This module does not add style conditioning and
does not change the rendered result.

Roles
-----
* IMAGE A — ``style_reference``  : appearance only; NEVER the geometry source.
* IMAGE B — ``target_building``  : the geometry authority; the actual FLUX
  img2img generation input (workflow node **300** → VAEEncode → KSampler).

Guarantees
----------
* Both images are resolved **only** from the verified request context
  (``context["references"]`` written by FACADE-02/03).
* Each role keeps an **independent** identity, filename, staged path and node
  id, even when the source filenames are identical.
* Binding is by **explicit node id** — the previous "assign the filename to
  every LoadImage node" behaviour is never used for dual-image workflows.
* IMAGE A can never overwrite node 300.
* Fail-closed: a missing / invalid / unstaged A or B **blocks** the dual-image
  request; there is no silent fallback to text2img and no image swap.
"""

import os

CONTRACT = "DualImageBindingV1"
VERSION = "1.0"

ROLE_A = "style_reference"
ROLE_B = "target_building"

#: The FACADE-02/03 transport contract keys ``context["references"]`` by the
#: ROLE LETTERS "A"/"B" (app.py), NOT by the binding layer's role names. A
#: role is resolved through this map, never by its own name.
CONTEXT_KEY_BY_ROLE = {
    ROLE_A: "A",
    ROLE_B: "B",
}

#: Node ids in the dual-image workflow template.
NODE_B = "300"          # IMAGE B — the generation input (unchanged)
NODE_A = "302"          # IMAGE A — a SEPARATE, explicit input node
NODE_A_ENCODE = "303"   # CLIPVisionEncode for A (UNCONSUMED — see below)

#: The exact node-id binding used by the dual-image graph.
DUAL_IMAGE_NODE_BINDINGS = {
    ROLE_A: NODE_A,
    ROLE_B: NODE_B,
}

#: The node the geometry authority must stay bound to.
GEOMETRY_NODE = NODE_B

#: Honest statement about the experimental reference branch.
REFERENCE_BRANCH_STATUS = (
    "unconsumed_clip_vision_output: node "
    + NODE_A_ENCODE
    + " is NOT connected to the sampler; ComfyUI may prune it and it proves "
    "no style conditioning and no execution."
)

#: Blocked reason codes emitted by the chat render dispatch. The two IMAGE B
#: codes are the FACADE-04C ones and are preserved EXACTLY; the IMAGE A codes
#: are the FACADE-04D.2 additions.
REASON_B_UNAVAILABLE = "target_building_image_unavailable"
REASON_B_NOT_STAGED = "target_building_image_not_staged"
REASON_A_UNAVAILABLE = "style_reference_image_unavailable"
REASON_A_NOT_STAGED = "style_reference_image_not_staged"
REASON_NOT_READY = "dual_image_binding_not_ready"


def fail_closed_reason(errors):
    """Map contract errors to the stable dispatch reason code.

    Fail-closed is by ROLE: a staging failure is reported distinctly from a
    missing/unreadable source, so the caller can tell "the file was not found"
    apart from "the copy into ComfyUI failed".
    """

    errors = [str(e) for e in (errors or [])]

    staging_failed = any(
        e.startswith(("staging_failed_", "staged_")) for e in errors
    )

    if any("target_building" in e for e in errors):
        return REASON_B_NOT_STAGED if staging_failed else REASON_B_UNAVAILABLE

    if any("style_reference" in e for e in errors):
        return REASON_A_NOT_STAGED if staging_failed else REASON_A_UNAVAILABLE

    return REASON_NOT_READY


def _reference_for(context, role):
    """One reference entry from the verified request context.

    The transport contract (FACADE-02/03) keys the references by the ROLE
    LETTERS "A"/"B"; this resolves the binding role through
    :data:`CONTEXT_KEY_BY_ROLE` so the two vocabularies can never silently
    drift apart.
    """

    if not isinstance(context, dict):
        return None

    references = context.get("references")

    if not isinstance(references, dict):
        return None

    key = CONTEXT_KEY_BY_ROLE.get(role)

    if key is None:
        return None

    entry = references.get(key)

    if not isinstance(entry, dict):
        return None

    return entry


def _stage(project_id, image_path, comfy_input=None):
    """Stage one image with the EXISTING ImageAssetBridge."""

    from core.render.image_asset_bridge import ImageAssetBridge

    bridge = ImageAssetBridge(comfy_input) if comfy_input else ImageAssetBridge()

    return bridge.register(project_id, image_path)


def build_dual_image_contract(
    context,
    project_id,
    stage_fn=None,
    comfy_input=None,
):
    """Build the role-bound A/B contract, or a fail-closed error result.

    ``stage_fn(project_id, image_path)`` may be injected for tests; by default
    the real ``ImageAssetBridge`` stages the file into the ComfyUI input dir.
    """

    result = {
        "contract": CONTRACT,
        "version": VERSION,
        "status": "blocked",
        "errors": [],
        "roles": {},
        "node_bindings": dict(DUAL_IMAGE_NODE_BINDINGS),
        "geometry_node": GEOMETRY_NODE,
        "reference_branch": REFERENCE_BRANCH_STATUS,
        "conditioning_active": False,
    }

    if not isinstance(project_id, str) or not project_id.strip():
        result["errors"].append("missing_project_context")
        return result

    if stage_fn is None:
        stage_fn = lambda pid, path: _stage(pid, path, comfy_input)

    for role in (ROLE_A, ROLE_B):

        entry = _reference_for(context, role)

        if not entry:
            result["errors"].append("missing_" + role)
            continue

        if not entry.get("present"):
            result["errors"].append("not_present_" + role)
            continue

        source_path = entry.get("path")

        if not source_path or not os.path.isfile(source_path):
            result["errors"].append("source_unreadable_" + role)
            continue

        try:
            staged = stage_fn(project_id, source_path)
        except Exception:
            result["errors"].append("staging_failed_" + role)
            continue

        if not isinstance(staged, dict) or staged.get("status") == "error":
            result["errors"].append("staging_failed_" + role)
            continue

        filename = staged.get("filename")

        if not filename:
            result["errors"].append("staged_filename_missing_" + role)
            continue

        # the staged file must really exist in the ComfyUI input directory
        staged_path = staged.get("path")

        if staged_path and not os.path.isfile(staged_path):
            result["errors"].append("staged_file_missing_" + role)
            continue

        result["roles"][role] = {
            "role": role,
            "authority": "appearance_only" if role == ROLE_A else "geometry",
            "asset_id": entry.get("asset_id"),
            "source_path": source_path,
            "filename": filename,
            "staged_path": staged_path,
            "node_id": DUAL_IMAGE_NODE_BINDINGS[role],
            # FACADE-02/03 transport provenance, for a traceable source-to-node
            # binding record on BOTH sides.
            "transport_key": CONTEXT_KEY_BY_ROLE[role],
            "transport_role": entry.get("role"),
            "provenance": entry.get("provenance") or "context.references",
        }

    if result["errors"]:
        return result

    a = result["roles"][ROLE_A]
    b = result["roles"][ROLE_B]

    # independent identities are mandatory, even with equal source names
    if a["node_id"] == b["node_id"]:
        result["errors"].append("role_node_collision")
        return result

    if a["filename"] == b["filename"] and a["asset_id"] == b["asset_id"]:
        result["errors"].append("role_identity_collision")
        return result

    result["status"] = "ready"
    return result


def bind_role_bindings(workflow, role_bindings):
    """Bind ``{role: {node_id, filename}}`` to EXPLICIT node ids.

    This is the SINGLE node-id binding implementation, shared by the contract
    helper (:func:`bind_images_to_workflow`) and the workflow injector. A role
    is written ONLY to the node id it names: it is never redirected to another
    node, and one filename is never broadcast to every ``LoadImage`` node.

    Returns ``(workflow, report)``. The binding is ATOMIC — if any requested
    role cannot be bound the ORIGINAL workflow is returned unmodified, so a
    partially bound graph can never be executed.
    """

    report = {
        "bound": {},
        "errors": [],
        "node_300_source": None,
    }

    if not isinstance(workflow, dict):
        report["errors"].append("invalid_workflow")
        return workflow, report

    if not isinstance(role_bindings, dict) or not role_bindings:
        report["errors"].append("no_role_bindings")
        return workflow, report

    import copy

    bound = copy.deepcopy(workflow)

    for role, binding in role_bindings.items():

        if not isinstance(binding, dict):
            report["errors"].append("binding_invalid_" + str(role))
            continue

        node_id = binding.get("node_id")

        filename = binding.get("filename")

        if node_id is None:
            report["errors"].append("binding_node_missing_" + str(role))
            continue

        node_id = str(node_id)

        node = bound.get(node_id)

        if not isinstance(node, dict) or node.get("class_type") != "LoadImage":
            report["errors"].append("binding_node_invalid_" + str(role))
            continue

        if not filename:
            report["errors"].append("binding_filename_missing_" + str(role))
            continue

        node.setdefault("inputs", {})["image"] = filename

        report["bound"][role] = {"node_id": node_id, "filename": filename}

    if report["errors"]:
        return workflow, report

    report["node_300_source"] = (
        (report["bound"].get(ROLE_B) or {}).get("filename")
    )

    return bound, report


def bind_images_to_workflow(workflow, contract):
    """Bind each role's filename to its EXPLICIT node id.

    Returns ``(workflow, report)``. Nothing is bound unless the contract is
    ``ready``; node 300 is never written by IMAGE A. Delegates the actual
    node-id write to :func:`bind_role_bindings` so there is exactly one
    binding implementation.
    """

    report = {
        "bound": {},
        "errors": list(contract.get("errors") or []),
        "node_300_source": None,
    }

    if not isinstance(contract, dict) or contract.get("status") != "ready":
        return workflow, report

    roles = contract.get("roles") or {}

    role_bindings = {}

    for role, node_id in (contract.get("node_bindings") or {}).items():

        role_bindings[role] = {
            "node_id": node_id,
            "filename": (roles.get(role) or {}).get("filename"),
        }

    return bind_role_bindings(workflow, role_bindings)


def dual_image_trace(contract, report=None):
    """Structured trace: sources, destinations, nodes, workflow selection."""

    roles = contract.get("roles") or {}

    def _side(role):
        entry = roles.get(role) or {}
        return {
            "source": entry.get("source_path"),
            "destination": entry.get("staged_path"),
            "filename": entry.get("filename"),
            "node_id": entry.get("node_id"),
            "asset_id": entry.get("asset_id"),
            "authority": entry.get("authority"),
        }

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "status": contract.get("status"),
        "errors": list(contract.get("errors") or []),
        "image_a": _side(ROLE_A),
        "image_b": _side(ROLE_B),
        "workflow": "flux_img2img_dual.json",
        "geometry_node": GEOMETRY_NODE,
        "geometry_source_node": (report or {}).get("node_300_source"),
        "conditioning_active": False,
        "reference_branch": REFERENCE_BRANCH_STATUS,
    }
