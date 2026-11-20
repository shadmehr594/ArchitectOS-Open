"""Pure vertex transform executor (Phase 3D-AF).

Consumes a validated raw OBJ loader result and a validated mesh transform spec
and produces transformed vertex POSITIONS plus transformed axis-aligned bounds.

This module is a pure asset-domain execution primitive. It deliberately does NOT:

- load meshes or build transform specs (it never imports those modules)
- reapply the DiffuScene -> ArchitectOS basis, the up-alignment component, the
  intrinsic yaw or the placement yaw
- recompose any rotation from angles (no trigonometry is performed here)
- transform or generate normals, reverse face winding, or triangulate faces
- infer external / raw-frame semantic handedness
- apply any non-identity scale
- insert anything into a scene, renderer, BIM or export structure
- touch the filesystem

It consumes ONLY the already-composed final affine metadata
(``final_rotation_matrix``, ``translation_xyz`` and ``matrix4x4``) and fails
closed when that metadata is malformed or mutually inconsistent.

The transform is position-only::

    v_world = R_final @ v_local + translation_xyz

Face index topology is copied verbatim; the source geometry is never mutated.
A proper rotation (det +1) is required, so no reflection can be introduced and
face winding is preserved automatically. Normals, winding semantics and
renderer-facing culling remain explicitly outside this phase.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Mapping


OUTPUT_TYPE = "transformed_mesh"

SOURCE_MESH_FRAME = "raw_mesh_local_frame"
DESTINATION_FRAME = "architectos_world_frame"

EXPECTED_LOADER_STATE = "mesh_loaded_valid"
# The only TransformSpec state in which the final affine metadata is present.
EXECUTABLE_SPEC_STATES = ("pending_mesh_alignment",)

IDENTITY_SCALE = (1.0, 1.0, 1.0)

STATE_READY = "transformed_vertices_ready"
STATE_BLOCKED = "transform_execution_blocked"

# Strict numeric tolerances for metadata self-consistency.
_MATRIX_ABS_TOL = 1e-9
_ORTHONORMAL_ABS_TOL = 1e-9
_DETERMINANT_ABS_TOL = 1e-9


# ---------------------------------------------------------------------------
# validation helpers
# ---------------------------------------------------------------------------

def _finite_scalar(value, label):
    """Return a finite float. ``bool`` is rejected despite subclassing int."""

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
    """Validate a numeric ``size`` x ``size`` matrix. Returns a NEW nested list."""

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


def _determinant3(matrix):
    return (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1]
        * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2]
        * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def _matvec3(matrix, vector):
    return [
        sum(matrix[row][col] * vector[col] for col in range(3))
        for row in range(3)
    ]


def _require_proper_rotation(matrix, label):
    """Require an orthonormal, proper (det +1) rotation.

    This validates the SUPPLIED affine only. It makes no claim about external
    dataset semantic handedness.
    """

    for left in range(3):
        for right in range(3):
            dot = sum(matrix[k][left] * matrix[k][right] for k in range(3))
            expected = 1.0 if left == right else 0.0
            if abs(dot - expected) > _ORTHONORMAL_ABS_TOL:
                raise ValueError(f"{label} must be orthonormal (R^T R = I)")

    determinant = _determinant3(matrix)
    if abs(determinant - 1.0) > _DETERMINANT_ABS_TOL:
        raise ValueError(
            f"{label} must be a proper rotation (det +1); a reflection is refused"
        )


def _require_matrix4x4_consistent(matrix, rotation, translation):
    """Require ``matrix4x4`` to encode exactly ``(rotation, translation)``.

    The executor never repairs inconsistent metadata and never silently prefers
    one representation over the other - a disagreement fails closed.
    """

    for row in range(3):
        for col in range(3):
            if abs(matrix[row][col] - rotation[row][col]) > _MATRIX_ABS_TOL:
                raise ValueError(
                    "transform.matrix4x4 upper-left 3x3 does not match "
                    "transform.final_rotation_matrix"
                )

    for row in range(3):
        if abs(matrix[row][3] - translation[row]) > _MATRIX_ABS_TOL:
            raise ValueError(
                "transform.matrix4x4 translation column does not match "
                "transform.translation_xyz"
            )

    for col in range(4):
        expected = 1.0 if col == 3 else 0.0
        if abs(matrix[3][col] - expected) > _MATRIX_ABS_TOL:
            raise ValueError(
                "transform.matrix4x4 last row must be [0, 0, 0, 1]"
            )


def _copy_vertices(vertices_xyz):
    """Return a NEW, validated, non-empty list of finite 3-vectors."""

    if isinstance(vertices_xyz, (str, bytes)) or not isinstance(
        vertices_xyz, (list, tuple)
    ):
        raise ValueError("geometry.vertices_xyz must be a list of 3-vectors")
    if len(vertices_xyz) == 0:
        raise ValueError("geometry.vertices_xyz must not be empty")

    return [
        _finite_vector3(vertex, "geometry.vertices_xyz") for vertex in vertices_xyz
    ]


def _copy_faces(faces, vertex_count):
    """Copy face indices verbatim: order, degree and winding are preserved.

    The raw loader contract is 0-based, in-range, non-empty index lists, so any
    deviation is a malformed input rather than something to normalize.
    """

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
            if item < 0 or item >= vertex_count:
                raise ValueError(
                    f"geometry.faces[{index}] index {item} is out of range"
                )
            row.append(item)
        copied.append(row)

    return copied


def _compute_bounds(vertices):
    """Axis-aligned bounds measured directly from transformed vertices."""

    minimum = [min(vertex[index] for vertex in vertices) for index in range(3)]
    maximum = [max(vertex[index] for vertex in vertices) for index in range(3)]

    return {
        "min_xyz": minimum,
        "max_xyz": maximum,
        "center_xyz": [
            (minimum[index] + maximum[index]) / 2.0 for index in range(3)
        ],
        "full_dims_xyz": [
            maximum[index] - minimum[index] for index in range(3)
        ],
    }


def _source_block(mesh_result):
    if not isinstance(mesh_result, Mapping):
        return {"source": None, "model_id": None, "raw_model_path": None}

    return {
        "source": mesh_result.get("source"),
        "model_id": mesh_result.get("model_id"),
        "raw_model_path": mesh_result.get("raw_model_path"),
    }


def _semantics(executed):
    return {
        "position_transform_executed": executed,
        "reflection_introduced": False,
        "normals_transformed": False,
        "face_winding_reversed": False,
        "external_raw_frame_handedness_inferred": False,
    }


def _blocked(mesh_result, reasons, placement_identity=None):
    """Valid-but-not-executable result. No geometry is emitted at all."""

    return {
        "type": OUTPUT_TYPE,
        "source": _source_block(mesh_result),
        "frames": {"source": SOURCE_MESH_FRAME, "destination": DESTINATION_FRAME},
        # Phase 3D-AH.1: propagated verbatim, even when no geometry is produced.
        "placement_identity": placement_identity,
        "geometry": None,
        "bounds": None,
        "transform": None,
        "topology": None,
        "semantics": _semantics(False),
        "status": {"state": STATE_BLOCKED, "reasons": list(reasons)},
    }


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def execute_mesh_transform(
    mesh_result: Mapping[str, Any],
    transform_spec: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the already-composed final affine to raw mesh vertex POSITIONS.

    ``mesh_result`` is a validated ``raw_obj_loader.load_raw_obj`` result;
    ``transform_spec`` is a ``mesh_transform_spec.build_mesh_transform_spec``
    result. Neither is called here, and neither is mutated.

    Returns a deterministic ``transformed_mesh`` dict on success, or a blocked
    result (``state = "transform_execution_blocked"``) when the metadata is
    well-formed but not execution-ready. Malformed metadata raises
    ``ValueError``. Partially transformed geometry is never returned.
    """

    if not isinstance(mesh_result, Mapping):
        raise ValueError("mesh_result must be a mapping")
    if not isinstance(transform_spec, Mapping):
        raise ValueError("transform_spec must be a mapping")

    # Phase 3D-AH.1: the placement identity is PROPAGATED unchanged from the
    # spec. The executor never regenerates it, never derives it from model_id,
    # and it never participates in the transform maths.
    placement_identity = copy.deepcopy(
        transform_spec.get("placement_identity")
    )

    # --- TransformSpec transform block -------------------------------------
    spec_transform = transform_spec.get("transform")
    if not isinstance(spec_transform, Mapping):
        # A blocked placement candidate emits ``transform = None``.
        return _blocked(mesh_result, ["spec_transform_missing"], placement_identity)

    # Scale must be identity. Malformed scale raises; a well-formed but
    # non-identity scale is a valid-but-not-executable state.
    scale_xyz = _finite_vector3(
        spec_transform.get("scale_xyz"), "transform.scale_xyz"
    )
    if any(
        value != identity for value, identity in zip(scale_xyz, IDENTITY_SCALE)
    ):
        return _blocked(
            mesh_result,
            ["non_identity_scale_not_executable"],
            placement_identity,
        )

    spec_status = transform_spec.get("status")
    spec_state = (
        spec_status.get("state") if isinstance(spec_status, Mapping) else None
    )
    if spec_state not in EXECUTABLE_SPEC_STATES:
        return _blocked(
            mesh_result,
            [f"spec_not_execution_ready:{spec_state}"],
            placement_identity,
        )

    if transform_spec.get("source_mesh_frame") != SOURCE_MESH_FRAME:
        raise ValueError(
            "transform_spec.source_mesh_frame must be raw_mesh_local_frame"
        )
    if transform_spec.get("destination_frame") != DESTINATION_FRAME:
        raise ValueError(
            "transform_spec.destination_frame must be architectos_world_frame"
        )

    final_rotation = spec_transform.get("final_rotation_matrix")
    translation = spec_transform.get("translation_xyz")
    matrix4x4 = spec_transform.get("matrix4x4")
    if final_rotation is None or translation is None or matrix4x4 is None:
        # e.g. an unresolved phi: the spec is complete but the affine is absent.
        return _blocked(
            mesh_result, ["final_affine_metadata_absent"], placement_identity
        )

    rotation = _matrix_rows(
        final_rotation, 3, "transform.final_rotation_matrix"
    )
    translation_xyz = _finite_vector3(
        translation, "transform.translation_xyz"
    )
    matrix = _matrix_rows(matrix4x4, 4, "transform.matrix4x4")

    _require_matrix4x4_consistent(matrix, rotation, translation_xyz)
    _require_proper_rotation(rotation, "transform.final_rotation_matrix")

    # --- mesh_result gates -------------------------------------------------
    loader_status = mesh_result.get("status")
    loader_state = (
        loader_status.get("state") if isinstance(loader_status, Mapping) else None
    )
    if loader_state != EXPECTED_LOADER_STATE:
        return _blocked(
            mesh_result,
            [f"loader_state_not_valid:{loader_state}"],
            placement_identity,
        )

    if mesh_result.get("mesh_frame") != SOURCE_MESH_FRAME:
        raise ValueError("mesh_result.mesh_frame must be raw_mesh_local_frame")

    geometry = mesh_result.get("geometry")
    if not isinstance(geometry, Mapping):
        raise ValueError("mesh_result.geometry must be a mapping")

    vertices = _copy_vertices(geometry.get("vertices_xyz"))
    faces = _copy_faces(geometry.get("faces"), len(vertices))

    # --- execute (position only) -------------------------------------------
    transformed = []
    for vertex in vertices:
        rotated = _matvec3(rotation, vertex)
        transformed.append(
            [
                rotated[0] + translation_xyz[0],
                rotated[1] + translation_xyz[1],
                rotated[2] + translation_xyz[2],
            ]
        )

    bounds = _compute_bounds(transformed)

    return {
        "type": OUTPUT_TYPE,
        "source": _source_block(mesh_result),
        "frames": {
            "source": SOURCE_MESH_FRAME,
            "destination": DESTINATION_FRAME,
        },
        # Phase 3D-AH.1: propagated verbatim from the spec. The downstream scene
        # instance consumes this for the final instance identity.
        "placement_identity": placement_identity,
        "geometry": {
            "vertices_xyz": transformed,
            "faces": faces,
        },
        "bounds": bounds,
        "transform": {
            "final_rotation_matrix": rotation,
            "translation_xyz": translation_xyz,
            "matrix4x4": matrix,
            "scale_xyz": list(IDENTITY_SCALE),
        },
        "topology": {
            "face_order_preserved": True,
            "vertex_count": len(transformed),
            "face_count": len(faces),
        },
        "semantics": _semantics(True),
        "status": {"state": STATE_READY, "reasons": []},
    }
