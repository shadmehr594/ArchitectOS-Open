"""Strict asset scene-instance container (Phase 3D-AH).

Wraps ONE already-transformed, world-space furniture mesh (the output of the
phase 3D-AF vertex executor) into a single strict scene-instance record.

The input ``transformed_mesh.geometry.vertices_xyz`` is ALREADY expressed in
``architectos_world_frame``: the DiffuScene placement basis, the raw-mesh up
alignment, the intrinsic yaw, the placement yaw and the translation are all
baked into those vertices. This module therefore applies NO transform at all.

This module deliberately does NOT:

- transform, re-transform, rotate, translate or scale any vertex
- apply the DiffuScene basis, the up alignment, phi or the placement yaw
- recompute or execute the executor matrix, or recompute bounds
- rename ``vertices_xyz`` to ``vertices``
- generate or transform normals, UVs, or reverse winding
- resolve MTL files, load textures, or choose a default shader
- validate floor contact, snap to a floor, or infer contact height
- verify, upgrade or reinterpret the coordinate unit
- insert anything into a scene, renderer, BIM or export structure
- read the filesystem

It is contract ownership only: validation plus defensive copying into one
immutable-in-practice record. The scene transform is explicit IDENTITY
metadata and is never multiplied into the vertices.

Instance identity is CONSUMED here, never invented (Phase 3D-AH.1). It comes
from a caller-supplied ``instance_id`` and/or the placement identity propagated
by the executor. ``model_id`` is ASSET MODEL identity - NOT scene instance
identity - so it is preserved separately and is never used to derive the
instance id.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Mapping


OUTPUT_TYPE = "asset_scene_instance"
OUTPUT_VERSION = "asset_scene_instance_v1"

EXPECTED_INPUT_TYPE = "transformed_mesh"
EXPECTED_INPUT_STATE = "transformed_vertices_ready"
GEOMETRY_FRAME = "architectos_world_frame"

SCENE_TRANSFORM_STATUS = "identity_world_space_mesh"
IDENTITY_SCALE = (1.0, 1.0, 1.0)

STATE_READY = "scene_instance_ready"

REQUIRED_INPUT_BLOCKS = (
    "source",
    "frames",
    "geometry",
    "bounds",
    "transform",
    "topology",
    "semantics",
    "status",
)

DEFAULT_UNITS = {"status": "unspecified"}
DEFAULT_MATERIAL = {"status": "unresolved"}
DEFAULT_SUPPORT = {"status": "unresolved"}

# A caller-supplied units mapping must never smuggle executable scale metadata:
# this phase does not authorise any scale, and the unit is not verified.
_FORBIDDEN_UNIT_KEYS = ("scale_xyz", "unit_scale", "executable_scale")


# ---------------------------------------------------------------------------
# validation helpers
# ---------------------------------------------------------------------------

def _finite_scalar(value, label):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a real number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a real number")
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")

    return number


def _finite_vector3(values, label):
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        raise ValueError(f"{label} must be a three-value vector")
    if len(values) != 3:
        raise ValueError(f"{label} must be a three-value vector")

    return [_finite_scalar(value, label) for value in values]


def _matrix_rows(matrix, size, label):
    if isinstance(matrix, (str, bytes)) or not isinstance(matrix, (list, tuple)):
        raise ValueError(f"{label} must be a {size}x{size} matrix")
    if len(matrix) != size:
        raise ValueError(f"{label} must be a {size}x{size} matrix")

    rows = []
    for row in matrix:
        if isinstance(row, (str, bytes)) or not isinstance(row, (list, tuple)):
            raise ValueError(f"{label} must be a {size}x{size} matrix")
        if len(row) != size:
            raise ValueError(f"{label} must be a {size}x{size} matrix")
        rows.append([_finite_scalar(value, f"{label} entry") for value in row])

    return rows


def _non_empty_string(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")

    return value


def _optional_string(value, label):
    if value is None:
        return None

    return _non_empty_string(value, label)


def _copy_vertices(vertices_xyz):
    if isinstance(vertices_xyz, (str, bytes)) or not isinstance(
        vertices_xyz, (list, tuple)
    ):
        raise ValueError("geometry.vertices_xyz must be a list of 3-vectors")
    if len(vertices_xyz) == 0:
        raise ValueError("geometry.vertices_xyz must not be empty")

    return [
        _finite_vector3(vertex, "geometry.vertices_xyz")
        for vertex in vertices_xyz
    ]


def _copy_faces(faces):
    """Defensive copy: order, degree and winding are preserved verbatim."""

    if isinstance(faces, (str, bytes)) or not isinstance(faces, (list, tuple)):
        raise ValueError("geometry.faces must be a list of index lists")

    copied = []
    for index, face in enumerate(faces):
        if isinstance(face, (str, bytes)) or not isinstance(face, (list, tuple)):
            raise ValueError(f"geometry.faces[{index}] must be an index list")
        if len(face) == 0:
            raise ValueError(f"geometry.faces[{index}] must not be empty")

        row = []
        for item in face:
            if isinstance(item, bool) or not isinstance(item, int):
                raise ValueError(
                    f"geometry.faces[{index}] must contain integer indices"
                )
            row.append(item)
        copied.append(row)

    return copied


def _copy_bounds(bounds):
    if not isinstance(bounds, Mapping):
        raise ValueError("bounds must be a mapping")

    minimum = _finite_vector3(bounds.get("min_xyz"), "bounds.min_xyz")
    maximum = _finite_vector3(bounds.get("max_xyz"), "bounds.max_xyz")
    center = _finite_vector3(bounds.get("center_xyz"), "bounds.center_xyz")
    dims = _finite_vector3(bounds.get("full_dims_xyz"), "bounds.full_dims_xyz")

    for index in range(3):
        if maximum[index] < minimum[index]:
            raise ValueError("bounds.max_xyz must be >= bounds.min_xyz")
        if dims[index] < 0.0:
            raise ValueError("bounds.full_dims_xyz must be non-negative")

    return {
        "min_xyz": minimum,
        "max_xyz": maximum,
        "center_xyz": center,
        "full_dims_xyz": dims,
    }


def _copy_topology(topology, vertex_count, face_count):
    if not isinstance(topology, Mapping):
        raise ValueError("topology must be a mapping")
    if topology.get("face_order_preserved") is not True:
        raise ValueError("topology.face_order_preserved must be True")
    if topology.get("vertex_count") != vertex_count:
        raise ValueError(
            "topology.vertex_count must equal len(geometry.vertices_xyz)"
        )
    if topology.get("face_count") != face_count:
        raise ValueError("topology.face_count must equal len(geometry.faces)")

    return {
        "face_order_preserved": True,
        "vertex_count": vertex_count,
        "face_count": face_count,
    }


def _validate_transform(transform):
    """Validate the executor transform block; never recompute or execute it."""

    if not isinstance(transform, Mapping):
        raise ValueError("transform must be a mapping")

    if transform.get("matrix4x4") is None:
        raise ValueError("transform.matrix4x4 is required")
    if transform.get("final_rotation_matrix") is None:
        raise ValueError("transform.final_rotation_matrix is required")
    if transform.get("translation_xyz") is None:
        raise ValueError("transform.translation_xyz is required")

    _matrix_rows(transform["matrix4x4"], 4, "transform.matrix4x4")
    _matrix_rows(
        transform["final_rotation_matrix"], 3, "transform.final_rotation_matrix"
    )
    _finite_vector3(transform["translation_xyz"], "transform.translation_xyz")

    scale = _finite_vector3(transform.get("scale_xyz"), "transform.scale_xyz")
    if any(value != identity for value, identity in zip(scale, IDENTITY_SCALE)):
        raise ValueError(
            "transform.scale_xyz must be identity [1.0, 1.0, 1.0]"
        )


def _optional_slot(value):
    """DiffuScene provenance slot: a non-empty string OR an integer.

    The slot is PROVENANCE ONLY. It never becomes instance identity, and it is
    never assumed to be globally unique - duplicate DiffuScene slot values are
    legitimate. ``bool`` is rejected despite subclassing ``int``.
    """

    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("slot must be a non-empty string or an integer")
    if isinstance(value, int):
        return value

    return _non_empty_string(value, "slot")


PLACEMENT_IDENTITY_RESOLVED = "resolved"
PLACEMENT_IDENTITY_UNRESOLVED = "unresolved"


def _resolve_instance_id(transformed_mesh, explicit_instance_id):
    """Resolve the scene instance id from the caller and the placement identity.

    The instance identity is CONSUMED, never derived from ``model_id``:

    1. an explicit ``instance_id`` is always allowed;
    2. a resolved placement identity contributes its own ``instance_id``;
    3. when both are present they must be identical, else ``ValueError``;
    4. when only the placement identity is resolved, it is used;
    5. when neither is available, ``ValueError`` - never a model_id fallback.
    """

    identity = transformed_mesh.get("placement_identity")

    propagated = None
    if identity is not None:
        if not isinstance(identity, Mapping):
            raise ValueError("placement_identity must be a mapping or None")
        status = identity.get("status")
        if status == PLACEMENT_IDENTITY_RESOLVED:
            propagated = _non_empty_string(
                identity.get("instance_id"), "placement_identity.instance_id"
            )
        elif status == PLACEMENT_IDENTITY_UNRESOLVED:
            if identity.get("instance_id") is not None:
                raise ValueError(
                    "unresolved placement_identity must not carry an instance_id"
                )
        else:
            raise ValueError(
                "placement_identity.status must be 'resolved' or 'unresolved'"
            )

    explicit = None
    if explicit_instance_id is not None:
        explicit = _non_empty_string(explicit_instance_id, "instance_id")

    if explicit is not None:
        if propagated is not None and explicit != propagated:
            raise ValueError(
                "instance_id does not match the resolved placement identity "
                f"instance_id: {explicit!r} != {propagated!r}"
            )

        return explicit

    if propagated is not None:
        return propagated

    # Fail closed: model_id is ASSET MODEL identity, so it can never stand in
    # for a scene instance identity.
    raise ValueError(
        "instance_id is required: no explicit instance_id was supplied and the "
        "placement identity is missing or unresolved (model_id must never be "
        "used as scene instance identity)"
    )


def _copy_optional_mapping(value, label, default, forbidden_keys=()):
    if value is None:
        return copy.deepcopy(default)
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    for key in forbidden_keys:
        if key in value:
            raise ValueError(
                f"{label} must not carry executable scale metadata: {key}"
            )

    return copy.deepcopy(dict(value))


def _identity_scene_transform():
    """Explicit IDENTITY scene transform. Metadata only - never applied."""

    return {
        "status": SCENE_TRANSFORM_STATUS,
        "position_xyz": [0.0, 0.0, 0.0],
        "rotation_xyz_rad": [0.0, 0.0, 0.0],
        "scale_xyz": [1.0, 1.0, 1.0],
        "must_not_reapply_asset_transform": True,
    }


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def build_asset_scene_instance(
    transformed_mesh: Mapping[str, Any],
    *,
    instance_id: str | None = None,
    category: str | None = None,
    slot: str | int | None = None,
    units: Mapping[str, Any] | None = None,
    material: Mapping[str, Any] | None = None,
    support: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap a transformed world-space mesh into one strict scene instance.

    ``transformed_mesh`` must be the output of the phase 3D-AF vertex executor.
    The builder validates it, then defensively copies geometry, bounds,
    topology and provenance. It never transforms, recomputes or executes
    anything, and it never mutates its inputs. Malformed input raises
    ``ValueError``.

    The caller cannot supply a placement yaw, phi, basis or any transform
    override: the scene transform is fixed IDENTITY metadata, because the mesh
    is already in ``architectos_world_frame``.

    The scene instance id comes from ``instance_id`` and/or the propagated
    placement identity; ``model_id`` is preserved separately as ASSET MODEL
    identity and is never used to build the instance id.
    """

    if not isinstance(transformed_mesh, Mapping):
        raise ValueError("transformed_mesh must be a mapping")

    if transformed_mesh.get("type") != EXPECTED_INPUT_TYPE:
        raise ValueError("transformed_mesh.type must be 'transformed_mesh'")

    for block in REQUIRED_INPUT_BLOCKS:
        if block not in transformed_mesh:
            raise ValueError(f"transformed_mesh is missing: {block}")

    frames = transformed_mesh["frames"]
    if not isinstance(frames, Mapping):
        raise ValueError("frames must be a mapping")
    if frames.get("destination") != GEOMETRY_FRAME:
        raise ValueError(
            "frames.destination must be 'architectos_world_frame'"
        )

    status = transformed_mesh["status"]
    if not isinstance(status, Mapping):
        raise ValueError("status must be a mapping")
    if status.get("state") != EXPECTED_INPUT_STATE:
        raise ValueError(
            "status.state must be 'transformed_vertices_ready'"
        )

    source_block = transformed_mesh["source"]
    if not isinstance(source_block, Mapping):
        raise ValueError("source must be a mapping")
    asset_source = _non_empty_string(source_block.get("source"), "source.source")
    model_id = _non_empty_string(source_block.get("model_id"), "source.model_id")
    raw_model_path = source_block.get("raw_model_path")
    if raw_model_path is not None and not isinstance(raw_model_path, str):
        raise ValueError("source.raw_model_path must be a string or None")

    geometry = transformed_mesh["geometry"]
    if not isinstance(geometry, Mapping):
        raise ValueError("geometry must be a mapping")
    if "vertices_xyz" not in geometry:
        raise ValueError("geometry is missing: vertices_xyz")
    if "faces" not in geometry:
        raise ValueError("geometry is missing: faces")

    vertices = _copy_vertices(geometry["vertices_xyz"])
    faces = _copy_faces(geometry["faces"])

    bounds = _copy_bounds(transformed_mesh["bounds"])
    topology = _copy_topology(
        transformed_mesh["topology"], len(vertices), len(faces)
    )

    _validate_transform(transformed_mesh["transform"])

    if not isinstance(transformed_mesh["semantics"], Mapping):
        raise ValueError("semantics must be a mapping")

    resolved_id = _resolve_instance_id(transformed_mesh, instance_id)

    classification = {
        "category": _optional_string(category, "category"),
        # Provenance slot: DiffuScene values may be integers and may repeat.
        "slot": _optional_slot(slot),
    }

    return {
        "type": OUTPUT_TYPE,
        "version": OUTPUT_VERSION,
        "instance_id": resolved_id,
        "asset": {
            "source": asset_source,
            "model_id": model_id,
            "raw_model_path": raw_model_path,
        },
        "classification": classification,
        "frames": {
            "geometry_frame": GEOMETRY_FRAME,
            "scene_transform_frame": GEOMETRY_FRAME,
        },
        "geometry": {
            "vertices_xyz": vertices,
            "faces": faces,
        },
        "bounds": bounds,
        "topology": topology,
        "scene_transform": _identity_scene_transform(),
        "provenance": {
            "executor_transform": copy.deepcopy(transformed_mesh["transform"]),
            "executor_semantics": copy.deepcopy(
                transformed_mesh["semantics"]
            ),
            "executor_status": copy.deepcopy(transformed_mesh["status"]),
            # Phase 3D-AH.1: the placement identity is preserved verbatim as
            # provenance - it is not recreated and not derived from model_id.
            "placement_identity": copy.deepcopy(
                transformed_mesh.get("placement_identity")
            ),
        },
        "units": _copy_optional_mapping(
            units,
            "units",
            DEFAULT_UNITS,
            forbidden_keys=_FORBIDDEN_UNIT_KEYS,
        ),
        "material": _copy_optional_mapping(
            material, "material", DEFAULT_MATERIAL
        ),
        "support": _copy_optional_mapping(
            support, "support", DEFAULT_SUPPORT
        ),
        "status": {"state": STATE_READY, "reasons": []},
    }
