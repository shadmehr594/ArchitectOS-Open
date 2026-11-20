"""Declarative mesh transform spec builder (Phase 3D-L).

Consumes a validated raw OBJ loader result and a placement candidate and emits
metadata only.

This module deliberately does NOT:

- transform mesh vertices or faces
- copy vertices/faces into the spec
- compute ``translation_xyz`` or ``matrix4x4``
- resolve the intrinsic forward / zero-facing orientation or the intrinsic yaw
  ``phi`` (i.e. the full ``R_mesh_alignment``)
- re-apply the placement basis (the adapter already did)
- create, derive or normalize the placement identity: it is COPIED verbatim
  from the placement candidate (Phase 3D-AH.1), never rebuilt from ``model_id``
- perform fit, unit or instance scaling
- read the filesystem or load the registry
- insert anything into a scene

The verified up-axis component is emitted as ``transform.up_alignment_matrix``
(``R_up``, mapping mesh ``+Y`` onto world ``+Z``) and described in
``orientation``. The full ``mesh_alignment_matrix``, ``translation_xyz`` and
``matrix4x4`` remain ``null`` because forward / zero-facing is unresolved.
Neither identity nor ``R_up`` is ever substituted for the full alignment.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Mapping


FORMAT_VERSION = "mesh_transform_v1"

SOURCE_MESH_FRAME = "raw_mesh_local_frame"
DESTINATION_FRAME = "architectos_world_frame"

EXPECTED_LOADER_STATE = "mesh_loaded_valid"
EXPECTED_INDEX_BASE = 0
EXPECTED_ROTATION_AXIS = "+Z"

# Established by FurnitureAdapter: the only transform-ready placement state.
# Its full vocabulary is ready_transform_metadata, pending_asset_match,
# pending_raw_model_path, invalid_source_position, invalid_source_rotation and
# invalid_source_dimensions.
EXPECTED_CANDIDATE_STATE = "ready_transform_metadata"

IDENTITY_SCALE = (1.0, 1.0, 1.0)

TRANSFORM_ORDER = (
    "subtract_local_bbox_center",
    "scale",
    "mesh_alignment",
    "placement_rotation",
    "translate_to_target",
)

STATE_BLOCKED = "transform_blocked"
STATE_PENDING_SCALE = "pending_scale_contract"
STATE_PENDING_ALIGNMENT = "pending_mesh_alignment"

# Verified in Phase 3D-N / 3D-N.1: raw 3D-FUTURE meshes are authored with +Y as
# the physical up axis (base plane pinned to Y = 0, horizontal extents centred).
RAW_MESH_UP_AXIS = "+Y"
RAW_MESH_UP_SIGN = "+"
RAW_MESH_UP_STATUS = "verified"
WORLD_UP_AXIS = "+Z"
UP_ALIGNMENT_VERIFIED = "verified"
UP_ALIGNMENT_STATUS = UP_ALIGNMENT_VERIFIED

# Verified in Phase 3D-O: no dataset-wide or category-wide forward / zero-facing
# convention could be established, so the intrinsic yaw stays unresolved and the
# full mesh alignment stays null.
FORWARD_STATUS = "unresolved"
INTRINSIC_YAW_STATUS = "unresolved"
FULL_ALIGNMENT_STATUS = "unresolved_forward"

# ArchitectOS canonical WORLD-facing target (Phase 3D-G / 3D-Z). This is a
# WORLD-frame declaration. The raw-mesh semantic facing is a different concept
# and is carried by ``forward_axis`` / ``forward_axis_frame``.
WORLD_ZERO_FACING_AXIS = "+X"
WORLD_ZERO_FACING_FRAME = DESTINATION_FRAME

# Phase 3D-AB: phi_result input vocabulary. Kept local to this module so the
# spec never imports the phi resolver; a test asserts the vocabularies agree.
PHI_STATUSES = ("resolved", "unresolved", "blocked")
PHI_STATUS_RESOLVED = "resolved"
PHI_STATUS_BLOCKED = "blocked"
PHI_FORWARD_STATUSES_WITH_AXIS = ("supported", "verified")
PHI_RESULT_KEYS = (
    "phi_status",
    "phi_rad",
    "forward_status",
    "forward_axis",
    "forward_axis_frame",
    "world_zero_facing_axis",
    "world_zero_facing_axis_frame",
    "reasons",
)

# Full-alignment states. A resolved phi does NOT complete the alignment: matrix
# composition is a separate, separately-authorised act.
FULL_ALIGNMENT_PENDING_MATRIX = "pending_matrix_composition"
FULL_ALIGNMENT_BLOCKED_PHI = "blocked_phi"
# Set once Rz(phi) * R_up has been composed. NOTE: this is matrix construction,
# NOT execution readiness - the matrix is not authorised for raw OBJ vertices
# while raw mesh handedness remains unresolved.
FULL_ALIGNMENT_MATRIX_CONSTRUCTED = "matrix_constructed"

# PARTIAL alignment component only: maps mesh +Y onto world +Z. This is a
# component of the mesh_alignment step, NOT the full mesh alignment. It must
# never be used as, or substituted for, mesh_alignment_matrix.
UP_ALIGNMENT_MATRIX = (
    (1.0, 0.0, 0.0),
    (0.0, 0.0, -1.0),
    (0.0, 1.0, 0.0),
)

# Compact, non-executable contract facts only. No sample model_ids and no audit
# data are carried here, and nothing in this tuple affects the transform.
FORWARD_EVIDENCE_NOTES = (
    "dataset_wide_forward_constant_not_verified",
    "seating_and_bed_plus_z_candidate_supported_but_unverified",
    "symmetric_assets_may_be_forward_unobservable",
)

# Phase 3D-R: forward observability state model. Purely declarative - none of
# these values is ever consumed when building transform values.
FORWARD_STATUSES = (
    "verified",
    "supported",
    "unresolved",
    "unobservable",
    "ambiguous",
    "unsupported",
)
FORWARD_AXES = ("+X", "-X", "+Z", "-Z")
FORWARD_SOURCES = (
    "geometry_measured",
    "family_rule",
    "per_asset_override",
    "none",
)
# A concrete axis is meaningful only for these states.
FORWARD_AXIS_REQUIRED_STATUSES = ("verified", "supported")
# Every other state must carry a null axis - no invented forward vector.
FORWARD_AXIS_NULL_STATUSES = (
    "unresolved",
    "unobservable",
    "ambiguous",
    "unsupported",
)
GEOMETRY_GATE_STATES = ("not_evaluated", "agreed", "disagreed")
# Per-asset geometry evidence states. ``ambiguous`` is representable but is not
# produced by the single-asset upper-structure metric: ambiguity is a
# family-level property (Phase 3D-Q), so it must be supplied by a caller.
GEOMETRY_EVIDENCE_STATES = ("observable", "unobservable", "ambiguous")
FORWARD_EVIDENCE_KEYS = ("rule_id", "geometry_gate", "agreement", "notes")
FORWARD_EVIDENCE_NOTE_MAX_CHARS = 200
FORWARD_CONTRACT_KEYS = (
    "status",
    "axis",
    "axis_frame",
    "source",
    "family",
    "evidence",
)


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


def _finite_triple(values, label):
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        raise ValueError(f"{label} must contain three values")
    if len(values) != 3:
        raise ValueError(f"{label} must contain three values")

    return [_finite_scalar(value, label) for value in values]


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _normalize_forward_evidence(evidence):
    """Validate and copy compact forward evidence.

    Compact by construction: a rule id, a gate outcome, an agreement ratio and
    short notes. Sample model ids and audit payloads are rejected by shape.
    """

    result = {
        "rule_id": None,
        "geometry_gate": "not_evaluated",
        "agreement": None,
        "notes": [],
    }
    if evidence is None:
        return result
    if not isinstance(evidence, Mapping):
        raise ValueError("forward evidence must be a mapping or None")

    unknown = set(evidence) - set(FORWARD_EVIDENCE_KEYS)
    if unknown:
        raise ValueError(
            "unknown forward evidence key(s): " + ", ".join(sorted(unknown))
        )

    if "rule_id" in evidence:
        value = evidence["rule_id"]
        if value is not None and (
            not isinstance(value, str) or not value.strip()
        ):
            raise ValueError(
                "forward evidence rule_id must be a non-empty string or None"
            )
        result["rule_id"] = value

    if "geometry_gate" in evidence:
        value = evidence["geometry_gate"]
        if value not in GEOMETRY_GATE_STATES:
            raise ValueError(
                "forward evidence geometry_gate must be one of: "
                + ", ".join(GEOMETRY_GATE_STATES)
            )
        result["geometry_gate"] = value

    if "agreement" in evidence:
        value = evidence["agreement"]
        if value is not None:
            number = _finite_scalar(value, "forward evidence agreement")
            if number < 0.0 or number > 1.0:
                raise ValueError(
                    "forward evidence agreement must be a ratio within [0, 1]"
                )
            result["agreement"] = number

    if "notes" in evidence:
        notes = evidence["notes"]
        if isinstance(notes, (str, bytes)) or not isinstance(
            notes, (list, tuple)
        ):
            raise ValueError("forward evidence notes must be a list of strings")
        cleaned = []
        for note in notes:
            if not isinstance(note, str):
                raise ValueError("forward evidence notes must be strings")
            if len(note) > FORWARD_EVIDENCE_NOTE_MAX_CHARS:
                raise ValueError(
                    "forward evidence notes must stay compact"
                )
            cleaned.append(note)
        result["notes"] = cleaned

    return result


def _build_forward_metadata(
    status="unresolved",
    axis=None,
    source="none",
    family=None,
    evidence=None,
    axis_frame=SOURCE_MESH_FRAME,
):
    """Build compact, validated, NON-EXECUTABLE forward metadata.

    The caller must supply every fact explicitly. No family or category
    detection happens here, and nothing in the result is read when building
    transform values.

    ``axis_frame`` is a required contract frame declaration - it states which
    frame the forward axis is expressed in. It is never inferred from geometry
    and no alternate frame is allowed in V1.
    """

    if axis_frame != SOURCE_MESH_FRAME:
        raise ValueError(
            f"axis_frame must be {SOURCE_MESH_FRAME!r}; no alternate forward "
            "axis frame is supported"
        )

    if status not in FORWARD_STATUSES:
        raise ValueError(
            "forward_status must be one of: " + ", ".join(FORWARD_STATUSES)
        )
    if axis is not None and axis not in FORWARD_AXES:
        raise ValueError(
            "forward_axis must be one of: " + ", ".join(FORWARD_AXES) + " or None"
        )
    if source not in FORWARD_SOURCES:
        raise ValueError(
            "forward_source must be one of: " + ", ".join(FORWARD_SOURCES)
        )
    if family is not None and (
        not isinstance(family, str) or not family.strip()
    ):
        raise ValueError("forward_family must be a non-empty string or None")

    if status in FORWARD_AXIS_REQUIRED_STATUSES:
        if axis is None:
            raise ValueError(
                f"forward_status {status!r} requires a concrete forward axis"
            )
    elif axis is not None:
        raise ValueError(
            f"forward_status {status!r} requires forward_axis to be null"
        )

    if source == "none" and axis is not None:
        raise ValueError("forward_source 'none' must not carry a forward axis")

    if source == "family_rule":
        if family is None:
            raise ValueError(
                "forward_source 'family_rule' requires a non-null forward_family"
            )
        if status == "verified":
            raise ValueError(
                "a family rule must not be marked 'verified' (Phase 3D-Q: the "
                "seating / adult-bed rule is SUPPORTED only)"
            )

    return {
        "forward_axis": axis,
        "forward_axis_frame": axis_frame,
        "forward_status": status,
        "forward_source": source,
        "forward_family": family,
        "forward_evidence": _normalize_forward_evidence(evidence),
    }


def _validate_phi_result(phi_result):
    """Validate a caller-supplied phi result structurally. Never normalizes.

    The spec validates, cross-checks and stores phi metadata - it never derives
    it. Malformed structure raises ``ValueError``.
    """

    if not isinstance(phi_result, Mapping):
        raise ValueError("phi_result must be a mapping")

    unknown = set(phi_result) - set(PHI_RESULT_KEYS)
    if unknown:
        raise ValueError(
            "unknown phi_result key(s): " + ", ".join(sorted(unknown))
        )

    for key in PHI_RESULT_KEYS:
        if key not in phi_result:
            raise ValueError(f"phi_result is missing: {key}")

    reasons = phi_result["reasons"]
    # Strictly a list: tuples, sets, dicts, strings, generators and None are all
    # rejected. The contract says "list", so nothing is normalized or coerced.
    if not isinstance(reasons, list):
        raise ValueError("phi_result reasons must be a list")

    status = phi_result["phi_status"]
    if status not in PHI_STATUSES:
        raise ValueError(
            "phi_result phi_status must be one of: " + ", ".join(PHI_STATUSES)
        )

    forward_axis_frame = phi_result["forward_axis_frame"]
    if forward_axis_frame != SOURCE_MESH_FRAME:
        raise ValueError(
            f"phi_result forward_axis_frame must be {SOURCE_MESH_FRAME!r}"
        )

    world_axis = phi_result["world_zero_facing_axis"]
    if world_axis != WORLD_ZERO_FACING_AXIS:
        raise ValueError(
            "phi_result world_zero_facing_axis must be "
            f"{WORLD_ZERO_FACING_AXIS!r}"
        )

    world_frame = phi_result["world_zero_facing_axis_frame"]
    if world_frame != WORLD_ZERO_FACING_FRAME:
        raise ValueError(
            "phi_result world_zero_facing_axis_frame must be "
            f"{WORLD_ZERO_FACING_FRAME!r}"
        )

    phi_rad = phi_result["phi_rad"]
    if status == PHI_STATUS_RESOLVED:
        if isinstance(phi_rad, bool) or not isinstance(phi_rad, (int, float)):
            raise ValueError("resolved phi_result requires a numeric phi_rad")
        phi_rad = float(phi_rad)
        if not math.isfinite(phi_rad):
            raise ValueError("resolved phi_result requires a finite phi_rad")
        if phi_result["forward_status"] not in PHI_FORWARD_STATUSES_WITH_AXIS:
            raise ValueError(
                "resolved phi_result requires forward_status 'supported' or "
                "'verified'"
            )
        if phi_result["forward_axis"] not in FORWARD_AXES:
            raise ValueError("resolved phi_result requires a valid forward_axis")
        # A resolved phi carries no reasons: reasons are reserved for the
        # non-resolved states. Accepting a non-empty list here would let a
        # caller smuggle an unvalidated explanation alongside a resolved value.
        if reasons:
            raise ValueError("resolved phi_result requires empty reasons")
    else:
        if phi_rad is not None:
            raise ValueError(
                f"phi_result phi_status {status!r} requires phi_rad to be null"
            )
        phi_rad = None
        if status == PHI_STATUS_BLOCKED and not reasons:
            raise ValueError("blocked phi_result requires non-empty reasons")

    return {
        "phi_status": status,
        "phi_rad": phi_rad,
        "forward_status": phi_result["forward_status"],
        "forward_axis": phi_result["forward_axis"],
        "forward_axis_frame": forward_axis_frame,
        "world_zero_facing_axis": world_axis,
        "world_zero_facing_axis_frame": world_frame,
        "reasons": list(reasons),
    }


def _cross_check_phi_result(phi_metadata, forward_metadata):
    """Require phi_result to describe the contract this spec already accepted."""

    mismatched = []
    for key in ("forward_status", "forward_axis", "forward_axis_frame"):
        if phi_metadata[key] != forward_metadata[key]:
            mismatched.append(key)

    if phi_metadata["world_zero_facing_axis"] != WORLD_ZERO_FACING_AXIS:
        mismatched.append("world_zero_facing_axis")
    if phi_metadata["world_zero_facing_axis_frame"] != WORLD_ZERO_FACING_FRAME:
        mismatched.append("world_zero_facing_axis_frame")

    if mismatched:
        raise ValueError(
            "phi_result does not match the resolved forward contract: "
            + ", ".join(mismatched)
        )

    return phi_metadata


def _validate_rotation_matrix(matrix, label):
    """Validate a numeric 3x3 matrix. Returns a NEW list-of-lists."""

    if isinstance(matrix, (str, bytes)) or not isinstance(matrix, (list, tuple)):
        raise ValueError(f"{label} must be a 3x3 matrix")
    if len(matrix) != 3:
        raise ValueError(f"{label} must be a 3x3 matrix")

    rows = []
    for row in matrix:
        if isinstance(row, (str, bytes)) or not isinstance(row, (list, tuple)):
            raise ValueError(f"{label} must be a 3x3 matrix")
        if len(row) != 3:
            raise ValueError(f"{label} must be a 3x3 matrix")
        rows.append([_finite_scalar(value, f"{label} entry") for value in row])

    return rows


def _compose_mesh_alignment_matrix(phi_rad, up_alignment_matrix):
    """Compose the intrinsic mesh alignment ``Rz(phi) * R_up``.

    Column-vector convention: ``R_up`` applies FIRST, ``Rz(phi)`` SECOND. The
    product contains the intrinsic mesh alignment ONLY - no placement yaw, no
    scale, no translation. Pure Python, no NumPy, no resolver or adapter import,
    no filesystem access, and neither input is mutated.
    """

    phi = _finite_scalar(phi_rad, "phi_rad")
    up = _validate_rotation_matrix(up_alignment_matrix, "up_alignment_matrix")

    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)
    rz = (
        (cos_phi, -sin_phi, 0.0),
        (sin_phi, cos_phi, 0.0),
        (0.0, 0.0, 1.0),
    )

    return [
        [
            sum(rz[row][k] * up[k][col] for k in range(3))
            for col in range(3)
        ]
        for row in range(3)
    ]


def _validate_vector3(vector, label):
    """Validate a finite numeric 3-vector. Returns a NEW list."""

    if isinstance(vector, (str, bytes)) or not isinstance(vector, (list, tuple)):
        raise ValueError(f"{label} must be a three-value vector")
    if len(vector) != 3:
        raise ValueError(f"{label} must be a three-value vector")

    return [_finite_scalar(value, f"{label} entry") for value in vector]


def _matmul3(left, right):
    """Pure 3x3 matrix product. Validates both inputs; returns a NEW matrix."""

    a = _validate_rotation_matrix(left, "left matrix")
    b = _validate_rotation_matrix(right, "right matrix")

    return [
        [
            sum(a[row][k] * b[k][col] for k in range(3))
            for col in range(3)
        ]
        for row in range(3)
    ]


def _matvec3(matrix, vector):
    """Pure 3x3-by-3 matrix-vector product. Returns a NEW list."""

    m = _validate_rotation_matrix(matrix, "matrix")
    v = _validate_vector3(vector, "vector")

    return [sum(m[row][k] * v[k] for k in range(3)) for row in range(3)]


def _compose_final_affine(
    mesh_alignment_matrix,
    placement_rotation_matrix,
    local_bbox_center_xyz,
    target_bbox_center_xyz,
):
    """Compose the final transform METADATA (never applied to vertices).

    Column-vector convention:

        R_final = R_place * R_mesh
        t       = c_w - R_final * c_m
        v_world = R_final * (v_local - c_m) + c_w

    ``c_m`` is the LOCAL BBOX CENTER - never the OBJ origin. Placement yaw
    appears exactly once (inside ``R_place``), ``R_up`` and phi appear exactly
    once each (inside ``R_mesh``), and the DiffuScene -> ArchitectOS basis ``B``
    is not applied here at all: the adapter already mapped the position basis.

    Pure Python, no NumPy, no filesystem, no resolver/adapter import, and no
    input is mutated.
    """

    final_rotation = _matmul3(placement_rotation_matrix, mesh_alignment_matrix)
    c_m = _validate_vector3(local_bbox_center_xyz, "local_bbox_center_xyz")
    c_w = _validate_vector3(target_bbox_center_xyz, "target_bbox_center_xyz")

    rotated_center = _matvec3(final_rotation, c_m)
    translation = [c_w[index] - rotated_center[index] for index in range(3)]

    return {
        "final_rotation_matrix": final_rotation,
        "translation_xyz": translation,
        "matrix4x4": [
            [
                final_rotation[0][0],
                final_rotation[0][1],
                final_rotation[0][2],
                translation[0],
            ],
            [
                final_rotation[1][0],
                final_rotation[1][1],
                final_rotation[1][2],
                translation[1],
            ],
            [
                final_rotation[2][0],
                final_rotation[2][1],
                final_rotation[2][2],
                translation[2],
            ],
            [0.0, 0.0, 0.0, 1.0],
        ],
    }


def _forward_contract_from_mapping(contract, label="forward_contract"):
    """Validate and normalize a caller-supplied forward contract mapping."""

    if not isinstance(contract, Mapping):
        raise ValueError(f"{label} must be a mapping or None")

    unknown = set(contract) - set(FORWARD_CONTRACT_KEYS)
    if unknown:
        raise ValueError(
            f"unknown {label} key(s): " + ", ".join(sorted(unknown))
        )

    if "axis_frame" not in contract:
        raise ValueError(f"{label} is missing: axis_frame")

    return _build_forward_metadata(
        status=contract.get("status", "unresolved"),
        axis=contract.get("axis"),
        source=contract.get("source", "none"),
        family=contract.get("family"),
        evidence=contract.get("evidence"),
        axis_frame=contract["axis_frame"],
    )


def resolve_forward_contract(
    family_contract,
    geometry_gate="not_evaluated",
    geometry_state=None,
):
    """Apply the accepted Phase 3D-S geometry agreement gate to a family rule.

    Metadata only, and non-executable. Geometry can only CONFIRM or REJECT the
    direction the family rule supplies - it never originates a semantic forward
    direction, and no direction is invented for a rejected rule.

    Only the accepted transitions are applied:

    ``supported`` + ``agreed``      -> ``supported`` with the family axis
    ``supported`` + ``disagreed``   -> ``unresolved`` with a null axis
    ``supported`` + ``unobservable``-> ``unobservable`` with a null axis
    ``supported`` + ``ambiguous``   -> ``ambiguous`` with a null axis

    Anything else falls back conservatively to ``unresolved`` with a null axis.
    A contract that is not ``supported`` is returned unchanged.
    """

    if geometry_gate not in GEOMETRY_GATE_STATES:
        raise ValueError(
            "geometry_gate must be one of: " + ", ".join(GEOMETRY_GATE_STATES)
        )
    if geometry_state is not None and geometry_state not in GEOMETRY_EVIDENCE_STATES:
        raise ValueError(
            "geometry_state must be one of: "
            + ", ".join(GEOMETRY_EVIDENCE_STATES)
            + " or None"
        )

    normalized = _forward_contract_from_mapping(family_contract, "family_contract")

    if normalized["forward_status"] == "supported":
        if geometry_gate == "agreed":
            status = "supported"
            axis = normalized["forward_axis"]
            note = "geometry_agrees_with_family_rule"
        elif geometry_gate == "disagreed":
            status = "unresolved"
            axis = None
            note = "geometry_disagrees_family_rule_rejected"
        elif geometry_state == "unobservable":
            status = "unobservable"
            axis = None
            note = "geometry_unobservable"
        elif geometry_state == "ambiguous":
            status = "ambiguous"
            axis = None
            note = "geometry_ambiguous"
        else:
            status = "unresolved"
            axis = None
            note = "geometry_gate_not_evaluated"
    else:
        # Only a SUPPORTED family rule is gated; nothing else is transitioned.
        status = normalized["forward_status"]
        axis = normalized["forward_axis"]
        note = "not_a_supported_family_rule"
        geometry_gate = "not_evaluated"

    evidence = dict(normalized["forward_evidence"])
    evidence["geometry_gate"] = geometry_gate
    evidence["notes"] = list(evidence["notes"]) + [note]

    # Returned in the same shape accepted by ``build_mesh_transform_spec``'s
    # ``forward_contract`` argument, so the two chain directly.
    resolved = {
        "status": status,
        "axis": axis,
        "axis_frame": normalized["forward_axis_frame"],
        "source": normalized["forward_source"],
        "family": normalized["forward_family"],
        "evidence": evidence,
    }

    # The resolver must never emit an impossible combination.
    _build_forward_metadata(**resolved)

    return resolved


def _orientation_metadata(
    forward_metadata=None, phi_metadata=None, matrix_constructed=False
):
    """Descriptive alignment contract.

    Purely declarative: nothing here is read when building transform values, so
    the evidence fields have zero effect on transform execution.

    ``mesh_alignment_matrix`` is deliberately absent: it already lives in
    ``transform`` and is not duplicated here.

    ``orientation.evidence`` holds GLOBAL contract facts (dataset-wide forward
    constant, phi verification). ``orientation.forward_evidence`` holds the
    compact PER-ASSET forward evidence. The two are different scopes and do not
    duplicate each other.
    """

    if forward_metadata is None:
        forward_metadata = _build_forward_metadata()

    if phi_metadata is None:
        phi_rad = None
        phi_status = INTRINSIC_YAW_STATUS
        full_alignment_status = FULL_ALIGNMENT_STATUS
    elif phi_metadata["phi_status"] == PHI_STATUS_RESOLVED:
        phi_rad = phi_metadata["phi_rad"]
        phi_status = PHI_STATUS_RESOLVED
        # "pending_matrix_composition" is only a defensive fallback: with
        # validated public inputs a resolved phi always composes, because the
        # up-alignment component is a verified constant.
        full_alignment_status = (
            FULL_ALIGNMENT_MATRIX_CONSTRUCTED
            if matrix_constructed
            else FULL_ALIGNMENT_PENDING_MATRIX
        )
    elif phi_metadata["phi_status"] == PHI_STATUS_BLOCKED:
        phi_rad = None
        phi_status = PHI_STATUS_BLOCKED
        full_alignment_status = FULL_ALIGNMENT_BLOCKED_PHI
    else:
        phi_rad = None
        phi_status = INTRINSIC_YAW_STATUS
        full_alignment_status = FULL_ALIGNMENT_STATUS

    return {
        "raw_mesh_up_axis": RAW_MESH_UP_AXIS,
        "raw_mesh_up_sign": RAW_MESH_UP_SIGN,
        "raw_mesh_up_status": RAW_MESH_UP_STATUS,
        "world_up_axis": WORLD_UP_AXIS,
        "up_alignment_status": UP_ALIGNMENT_STATUS,
        "forward_axis": forward_metadata["forward_axis"],
        # Frame declaration for forward_axis, copied from the normalized forward
        # metadata - never guessed here.
        "forward_axis_frame": forward_metadata["forward_axis_frame"],
        "forward_status": forward_metadata["forward_status"],
        "forward_source": forward_metadata["forward_source"],
        "forward_family": forward_metadata["forward_family"],
        "forward_evidence": forward_metadata["forward_evidence"],
        # ArchitectOS canonical WORLD-facing target. Distinct from the raw-mesh
        # semantic facing, which is carried by forward_axis / forward_axis_frame.
        # The legacy ambiguous ``zero_facing_axis`` / ``zero_facing_status``
        # fields were removed in Phase 3D-AA.
        "world_zero_facing_axis": WORLD_ZERO_FACING_AXIS,
        "world_zero_facing_axis_frame": WORLD_ZERO_FACING_FRAME,
        "intrinsic_yaw_phi_rad": phi_rad,
        "intrinsic_yaw_status": phi_status,
        "full_alignment_status": full_alignment_status,
        "evidence": {
            "state": "unresolved",
            "dataset_wide_constant": False,
            "numeric_phi_verified": False,
            "notes": list(FORWARD_EVIDENCE_NOTES),
        },
    }


def _result_stub(mesh_result, placement_candidate, world_reference):
    position = _mapping(placement_candidate.get("position"))

    return {
        "format_version": FORMAT_VERSION,
        "source_mesh_frame": SOURCE_MESH_FRAME,
        "destination_frame": DESTINATION_FRAME,
        "mesh_reference": {
            "model_id": mesh_result.get("model_id"),
            "raw_model_path": mesh_result.get("raw_model_path"),
        },
        "source_center_is_basis_mapped": True,
        "basis": {
            "version": position.get("basis"),
            "already_applied": True,
        },
        # Optional future world reference. Never used to alter the target in
        # this phase; room_local_xyz remains the authoritative target.
        "world_reference": world_reference,
        # Phase 3D-AH.1: placement identity is COPIED verbatim from the placement
        # candidate. This module never creates, derives, normalizes or repairs
        # it - in particular it is never derived from ``model_id``, which is
        # ASSET MODEL identity, not scene instance identity. When the candidate
        # carries no identity the value stays ``None`` (explicitly absent), and
        # it is still emitted on blocked specs so the identity survives the
        # status gates as provenance.
        "placement_identity": copy.deepcopy(
            placement_candidate.get("placement_identity")
        ),
        "orientation": None,
        "pivot": None,
        "transform": None,
        "bounds_before": None,
        "bounds_after_partial": None,
        "rotation_completeness": None,
        "status": {"state": None, "reasons": []},
    }


def _blocked(spec, reasons):
    """No transform metadata is emitted for a blocked spec."""

    spec["pivot"] = None
    spec["transform"] = None
    spec["orientation"] = None
    spec["bounds_before"] = None
    spec["bounds_after_partial"] = None
    spec["rotation_completeness"] = None
    spec["status"] = {"state": STATE_BLOCKED, "reasons": reasons}

    return spec


def _placement_rotation_matrix(yaw_rad):
    """R_z(yaw_rad): rotation about the ArchitectOS world +Z axis."""

    cos_yaw = math.cos(yaw_rad)
    sin_yaw = math.sin(yaw_rad)

    return [
        [cos_yaw, -sin_yaw, 0.0],
        [sin_yaw, cos_yaw, 0.0],
        [0.0, 0.0, 1.0],
    ]


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def build_mesh_transform_spec(
    mesh_result: Mapping[str, Any],
    placement_candidate: Mapping[str, Any],
    forward_contract: Mapping[str, Any] | None = None,
    phi_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a declarative, metadata-only mesh transform spec.

    ``forward_contract`` is OPTIONAL, non-executable forward metadata supplied
    by the caller (``status``, ``axis``, ``axis_frame``, ``source``, ``family``,
    ``evidence``). It is validated and copied only - never computed, inferred or
    executed. When omitted, forward stays ``unresolved`` with a null axis.

    ``phi_result`` is OPTIONAL, already-resolved intrinsic yaw metadata produced
    by the caller (see ``mesh_alignment_resolver.resolve_intrinsic_yaw_phi``).
    It is validated, cross-checked against the resolved forward contract and
    world-facing target, and STORED as metadata only. This function never calls
    the phi resolver, never composes a matrix and never transforms vertices.

    A malformed ``forward_contract`` or ``phi_result`` raises ``ValueError``.

    Pure function: no filesystem access, no registry loading, no vertex
    transformation. Expected data conditions return ``transform_blocked``;
    malformed container arguments raise ``ValueError``.
    """

    if not isinstance(mesh_result, Mapping):
        raise ValueError("mesh_result must be a mapping")
    if not isinstance(placement_candidate, Mapping):
        raise ValueError("placement_candidate must be a mapping")

    forward_metadata = _build_forward_metadata()
    if forward_contract is not None:
        forward_metadata = _forward_contract_from_mapping(forward_contract)

    position = _mapping(placement_candidate.get("position"))
    rotation = _mapping(placement_candidate.get("rotation"))
    scale = _mapping(placement_candidate.get("scale"))

    world_reference = {"world_xyz": None, "authoritative": False}
    raw_world_xyz = position.get("world_xyz")

    reasons: list[str] = []

    # --- loader provenance -------------------------------------------------
    loader_status = _mapping(mesh_result.get("status"))
    loader_state = loader_status.get("state")
    if loader_state != EXPECTED_LOADER_STATE:
        reasons.append(f"loader_state_not_valid:{loader_state}")

    if mesh_result.get("mesh_frame") != SOURCE_MESH_FRAME:
        reasons.append("mesh_frame_not_raw_mesh_local_frame")

    geometry = _mapping(mesh_result.get("geometry"))
    if geometry.get("index_base") != EXPECTED_INDEX_BASE:
        reasons.append("geometry_index_base_not_zero")

    # --- placement candidate status ---------------------------------------
    candidate_status = placement_candidate.get("status")
    if not isinstance(candidate_status, Mapping):
        reasons.append("placement_candidate_status_missing")
    else:
        candidate_state = candidate_status.get("state")
        if candidate_state is None:
            reasons.append("placement_candidate_status_state_missing")
        elif candidate_state != EXPECTED_CANDIDATE_STATE:
            reasons.append(
                "placement_candidate_state_not_transform_ready:"
                f"{candidate_state}"
            )

    # --- pivot -------------------------------------------------------------
    mesh_origin_xyz = None
    local_bbox_center_xyz = None
    pivot = mesh_result.get("pivot")
    if not isinstance(pivot, Mapping):
        reasons.append("loader_pivot_missing")
    else:
        try:
            mesh_origin_xyz = _finite_triple(
                pivot.get("mesh_origin_xyz"), "pivot.mesh_origin_xyz"
            )
            local_bbox_center_xyz = _finite_triple(
                pivot.get("bbox_center_xyz"), "pivot.bbox_center_xyz"
            )
        except ValueError as error:
            reasons.append(f"invalid_pivot:{error}")

    # --- bounds ------------------------------------------------------------
    bounds_before = None
    bounds = mesh_result.get("bounds")
    if not isinstance(bounds, Mapping):
        reasons.append("loader_bounds_missing")
    else:
        try:
            bounds_before = {
                "min_xyz": _finite_triple(bounds.get("min_xyz"), "bounds.min_xyz"),
                "max_xyz": _finite_triple(bounds.get("max_xyz"), "bounds.max_xyz"),
                "dims_xyz": _finite_triple(bounds.get("dims_xyz"), "bounds.dims_xyz"),
                "center_xyz": _finite_triple(
                    bounds.get("center_xyz"), "bounds.center_xyz"
                ),
            }
        except ValueError as error:
            reasons.append(f"invalid_bounds:{error}")

    # --- placement center --------------------------------------------------
    # The adapter already applied the placement basis, so room_local_xyz is
    # consumed as-is. B is NOT applied again here.
    target_bbox_center_xyz = None
    try:
        target_bbox_center_xyz = _finite_triple(
            position.get("room_local_xyz"), "position.room_local_xyz"
        )
    except ValueError as error:
        reasons.append(f"invalid_placement_center:{error}")

    # --- placement rotation ------------------------------------------------
    yaw_rad = None
    try:
        yaw_rad = _finite_scalar(rotation.get("yaw_rad"), "rotation.yaw_rad")
    except ValueError as error:
        reasons.append(f"invalid_placement_rotation:{error}")

    if rotation.get("axis") != EXPECTED_ROTATION_AXIS:
        reasons.append("rotation_axis_not_plus_z")

    # --- optional world reference -----------------------------------------
    if raw_world_xyz is not None:
        try:
            world_reference["world_xyz"] = _finite_triple(
                raw_world_xyz, "position.world_xyz"
            )
        except ValueError as error:
            reasons.append(f"invalid_world_reference:{error}")

    # --- scale -------------------------------------------------------------
    scale_xyz = None
    scale_not_identity = False
    try:
        scale_xyz = _finite_triple(scale.get("scale_xyz"), "scale.scale_xyz")
        scale_not_identity = not all(
            value == identity for value, identity in zip(scale_xyz, IDENTITY_SCALE)
        )
    except ValueError as error:
        reasons.append(f"invalid_scale:{error}")

    spec = _result_stub(mesh_result, placement_candidate, world_reference)

    if reasons:
        return _blocked(spec, reasons)

    spec["pivot"] = {
        "mesh_origin_xyz": mesh_origin_xyz,
        "local_bbox_center_xyz": local_bbox_center_xyz,
        "target_bbox_center_xyz": target_bbox_center_xyz,
    }
    spec["bounds_before"] = bounds_before

    if scale_not_identity:
        # Non-identity scale is not accepted: no transform is calculated at all.
        spec["transform"] = {
            "order": list(TRANSFORM_ORDER),
            "scale_xyz": scale_xyz,
            "up_alignment_matrix": None,
            "mesh_alignment_matrix": None,
            "placement_rotation_matrix": None,
            "final_rotation_matrix": None,
            "translation_xyz": None,
            "matrix4x4": None,
        }
        spec["status"] = {
            "state": STATE_PENDING_SCALE,
            "reasons": ["scale_not_identity"],
        }

        return spec

    # phi is validated and cross-checked only on the path where it would be
    # stored, so the placement-status and scale-status gates keep precedence.
    phi_metadata = None
    if phi_result is not None:
        phi_metadata = _cross_check_phi_result(
            _validate_phi_result(phi_result), forward_metadata
        )

    # Intrinsic mesh alignment is composed ONLY when the phi result is resolved
    # AND the up-alignment component is verified. Nothing is derived here: phi
    # was supplied and cross-checked above.
    mesh_alignment_matrix = None
    if (
        phi_metadata is not None
        and phi_metadata["phi_status"] == PHI_STATUS_RESOLVED
        and UP_ALIGNMENT_STATUS == UP_ALIGNMENT_VERIFIED
    ):
        mesh_alignment_matrix = _compose_mesh_alignment_matrix(
            phi_metadata["phi_rad"], UP_ALIGNMENT_MATRIX
        )

    # The placement rotation is computed ONCE and shared by the emitted field and
    # the affine composition, so the yaw can never be applied twice.
    placement_rotation_matrix = _placement_rotation_matrix(yaw_rad)

    # Final transform METADATA. Composed only when the intrinsic mesh alignment
    # exists; the pivot is the LOCAL BBOX CENTER, never the OBJ origin. This is
    # metadata only - no vertex is transformed and nothing becomes executable.
    final_rotation_matrix = None
    translation_xyz = None
    matrix4x4 = None
    if mesh_alignment_matrix is not None:
        affine = _compose_final_affine(
            mesh_alignment_matrix,
            placement_rotation_matrix,
            local_bbox_center_xyz,
            target_bbox_center_xyz,
        )
        final_rotation_matrix = affine["final_rotation_matrix"]
        translation_xyz = affine["translation_xyz"]
        matrix4x4 = affine["matrix4x4"]

    spec["transform"] = {
        "order": list(TRANSFORM_ORDER),
        "scale_xyz": list(IDENTITY_SCALE),
        # Partial up-axis component only.
        "up_alignment_matrix": [list(row) for row in UP_ALIGNMENT_MATRIX],
        # Intrinsic mesh alignment only: Rz(phi) * R_up. Never contains the
        # placement yaw, scale or translation. Stays None unless phi is resolved.
        # NOTE: construction is NOT execution readiness - raw mesh handedness is
        # still unresolved, so this matrix must not be applied to raw vertices.
        "mesh_alignment_matrix": mesh_alignment_matrix,
        "placement_rotation_matrix": placement_rotation_matrix,
        # Final affine metadata: R_final = R_place * R_mesh and
        # t = c_w - R_final * c_m. Metadata only; never applied to vertices.
        "final_rotation_matrix": final_rotation_matrix,
        "translation_xyz": translation_xyz,
        "matrix4x4": matrix4x4,
    }
    spec["orientation"] = _orientation_metadata(
        forward_metadata, phi_metadata, mesh_alignment_matrix is not None
    )
    spec["rotation_completeness"] = "placement_only"

    if matrix4x4 is None:
        alignment_reasons = ["mesh_alignment_unresolved"]
    elif final_rotation_matrix is None:
        # Defensive only: an intrinsic alignment without a composed final affine.
        alignment_reasons = [
            "mesh_alignment_not_executable",
            "mesh_handedness_unresolved",
        ]
    else:
        # The final affine metadata exists, so claiming the alignment is
        # "unresolved" would be false. It is still NOT authorised for raw OBJ
        # vertex execution: the raw-frame handedness / semantic frame
        # authorization boundary remains unresolved. Matrix construction is not
        # execution readiness, so the state stays deliberately pending.
        alignment_reasons = [
            "mesh_transform_not_executable",
            "mesh_handedness_unresolved",
        ]

    if world_reference["world_xyz"] is not None:
        alignment_reasons.append("world_reference_recorded_not_applied")

    spec["status"] = {
        "state": STATE_PENDING_ALIGNMENT,
        "reasons": alignment_reasons,
    }

    return spec
