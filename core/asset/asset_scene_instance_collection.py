"""Deterministic asset scene-instance collection contract (Phase 3D-AJ).

Groups an ordered batch of already-built ``asset_scene_instance`` objects into
ONE validated, deterministic collection.

Each member is already WORLD-SPACE geometry: the DiffuScene placement basis, the
raw-mesh up alignment, the intrinsic yaw, the placement yaw and the translation
are all baked into its vertices, and its ``scene_transform`` is explicit
IDENTITY metadata. The collection therefore applies NO transform at all.

This module is a pure container + validation contract. It deliberately does NOT:

- build meshes, load OBJ files, or read the filesystem
- generate or reinterpret placement identity
- transform vertices, recompute bounds, or alter faces/winding
- recompose or apply any matrix (basis ``B``, ``R_up``, ``phi``, placement yaw,
  ``matrix4x4``) or the identity ``scene_transform``
- resolve materials or textures
- validate support, floor contact, collision, clearance or room containment
- claim renderability or export readiness
- sanitize or export ``asset.raw_model_path``
- insert anything into a scene, renderer, BIM, ``scene_result`` or export result
- call ``FurnitureAdapter``, ``mesh_transform_spec`` or
  ``mesh_transform_executor``
- use randomness, UUIDs, timestamps, geometry hashes, or a global counter

Memory ownership: every member is DEEP-COPIED on the way in, so a caller can
never mutate the collection afterwards by mutating the objects it passed in, and
collection members never alias each other.

Ordering: input order is preserved EXACTLY - no sorting, grouping or
canonicalization. The collection ordinal IS the input list position; it is
deliberately NOT injected into member copies, so each member stays a faithful,
unmodified ``asset_scene_instance`` contract.

Identity: ``asset.model_id`` is ASSET MODEL identity and may legitimately repeat
across members; ``classification.slot`` is provenance only and may also repeat.
Only ``instance_id`` must be unique, and duplicates FAIL CLOSED.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping


OUTPUT_TYPE = "asset_scene_instance_collection"
OUTPUT_VERSION = "asset_scene_instance_collection_v1"

EXPECTED_INSTANCE_TYPE = "asset_scene_instance"

STATE_READY = "asset_instance_collection_ready"


# ---------------------------------------------------------------------------
# validation helpers
# ---------------------------------------------------------------------------

def _non_empty_string(value, label):
    """Return a non-empty string unchanged, else raise.

    ``bool`` is rejected explicitly: a boolean is never a valid identifier.
    """

    if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")

    return value


def _copy_context(context):
    """Deep-copy optional context. Missing context is never inferred."""

    if context is None:
        return None
    if not isinstance(context, Mapping):
        raise ValueError("context must be a mapping or None")

    return copy.deepcopy(dict(context))


def _copy_instances(instances):
    """Validate container integrity and deep-copy each member in input order.

    Container integrity ONLY: list, mapping members, instance type and a unique
    non-empty ``instance_id``. Member internals are deliberately not
    re-validated here - that is the instance contract's job, not the
    collection's.
    """

    if not isinstance(instances, list):
        raise ValueError("instances must be a list")

    copied = []
    seen_instance_ids = set()

    for index, instance in enumerate(instances):
        if not isinstance(instance, Mapping):
            raise ValueError(f"instances[{index}] must be a mapping")

        if instance.get("type") != EXPECTED_INSTANCE_TYPE:
            raise ValueError(
                f"instances[{index}].type must be {EXPECTED_INSTANCE_TYPE!r}"
            )

        instance_id = instance.get("instance_id")
        if (
            isinstance(instance_id, bool)
            or not isinstance(instance_id, str)
            or not instance_id.strip()
        ):
            raise ValueError(
                f"instances[{index}].instance_id must be a non-empty string"
            )

        if instance_id in seen_instance_ids:
            raise ValueError(f"duplicate instance_id: {instance_id!r}")
        seen_instance_ids.add(instance_id)

        # Deep copy: the collection owns its own memory and never aliases the
        # caller's objects. No key is added or removed.
        copied.append(copy.deepcopy(dict(instance)))

    return copied


def _semantics():
    """Static, declarative contract facts. Nothing here is executable."""

    return {
        "world_space_geometry": True,
        "transforms_already_applied": True,
        "scene_transform_application_required": False,
        "duplicate_instance_ids_allowed": False,
        "input_order_preserved": True,
        "room_context_required": False,
        "physical_validation_complete": False,
        "render_ready": False,
        "export_ready": False,
    }


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def build_asset_scene_instance_collection(
    instances,
    *,
    collection_id=None,
    context=None,
):
    """Wrap an ordered batch of ``asset_scene_instance`` objects into ONE
    deterministic collection.

    ``instances`` must be a list of mappings whose ``type`` is
    ``"asset_scene_instance"`` and whose ``instance_id`` is a unique non-empty
    string. Order is preserved exactly; duplicates raise ``ValueError`` and are
    never deduplicated, overwritten or renamed.

    ``collection_id`` is OPTIONAL and preserved verbatim when supplied; when
    omitted it stays ``None`` - no identity is invented. ``context`` is OPTIONAL
    metadata, deep-copied and never inferred or used to change geometry or
    identity.

    Pure function: no filesystem, no global mutable state, no randomness, no
    UUID, no timestamp, and no geometry or transform work of any kind.
    """

    copied_instances = _copy_instances(instances)

    if collection_id is None:
        resolved_collection_id = None
    else:
        resolved_collection_id = _non_empty_string(collection_id, "collection_id")

    resolved_context = _copy_context(context)

    return {
        "type": OUTPUT_TYPE,
        "version": OUTPUT_VERSION,
        "collection_id": resolved_collection_id,
        "instances": copied_instances,
        "count": len(copied_instances),
        "instance_ids": [
            instance["instance_id"] for instance in copied_instances
        ],
        "context": resolved_context,
        "semantics": _semantics(),
        "status": {"state": STATE_READY, "reasons": []},
    }
