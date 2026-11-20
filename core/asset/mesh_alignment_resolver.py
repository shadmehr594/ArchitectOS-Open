"""Pure intrinsic yaw (phi) resolver (Phase 3D-Y).

Derives the mesh-intrinsic yaw ``phi`` from ALREADY-RESOLVED semantic forward
metadata only:

    R_mesh_alignment = Rz(phi) * R_up
    R_up = Rx(+90 deg) = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]

``R_up`` maps the raw mesh axes to the world: raw +X -> world +X, raw +Y ->
world +Z (verified up), raw +Z -> world -Y, raw -Z -> world +Y. The required
``phi`` is the world-Z yaw that brings the resolved RAW-frame semantic forward
onto the declared ArchitectOS WORLD zero-facing target (``+X``).

The raw-facing and world-facing concepts are deliberately separate: the raw
semantic facing arrives as ``forward_contract.axis`` (raw frame), while the
world target arrives as ``world_zero_facing_axis`` (world frame) and is echoed
with its own frame tag.

SAFETY BOUNDARY: this module never receives or measures geometry. It accepts no
vertices, no geometry evidence, and no expected geometry direction, so the
forbidden derivations (geometry -> phi, expected_geometry_direction -> phi) are
structurally impossible rather than merely prohibited. Semantic forward must
already have come from an explicit rule or caller contract.

This module emits phi METADATA only. It does not populate
``intrinsic_yaw_phi_rad``, ``mesh_alignment_matrix``, ``matrix4x4`` or
``translation_xyz``, and it never transforms vertices.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from core.asset.mesh_transform_spec import (
    FORWARD_CONTRACT_KEYS,
    FORWARD_STATUSES,
    SOURCE_MESH_FRAME,
    WORLD_ZERO_FACING_AXIS,
    WORLD_ZERO_FACING_FRAME,
)


UP_ALIGNMENT_VERIFIED = "verified"
# The ArchitectOS WORLD canonical forward target. This is a world-frame value;
# the raw-mesh semantic facing is carried separately by forward_contract.axis.
SUPPORTED_WORLD_ZERO_FACING_AXIS = WORLD_ZERO_FACING_AXIS

PHI_STATUS_RESOLVED = "resolved"
PHI_STATUS_UNRESOLVED = "unresolved"
PHI_STATUS_BLOCKED = "blocked"

# Transform math, not semantic knowledge: the yaw that maps each permitted
# raw-frame forward axis onto world +X after R_up. Derived from
# Rz(phi) * R_up * f_raw = (1, 0, 0); see the 3D-X audit for the derivation.
PHI_BY_RAW_FORWARD = {
    "+X": 0.0,
    "-X": math.pi,
    "+Z": math.pi / 2.0,
    "-Z": -math.pi / 2.0,
}

# Contract statuses that assert a forward axis.
FORWARD_STATUSES_WITH_AXIS = ("supported", "verified")
# Contract statuses that assert no forward direction.
FORWARD_STATUSES_WITHOUT_AXIS = (
    "unresolved",
    "unobservable",
    "ambiguous",
    "unsupported",
)

_REQUIRED_CONTRACT_KEYS = ("status", "axis", "axis_frame")


def _validate_contract(forward_contract):
    if not isinstance(forward_contract, Mapping):
        raise ValueError("forward_contract must be a mapping")

    unknown = set(forward_contract) - set(FORWARD_CONTRACT_KEYS)
    if unknown:
        raise ValueError(
            "unknown forward_contract field(s): " + ", ".join(sorted(unknown))
        )

    for key in _REQUIRED_CONTRACT_KEYS:
        if key not in forward_contract:
            raise ValueError(f"forward_contract is missing: {key}")

    # A frame declaration is contract structure, not a runtime uncertainty, so a
    # malformed or missing frame is a hard error - never a "blocked" state.
    if forward_contract["axis_frame"] != SOURCE_MESH_FRAME:
        raise ValueError(
            f"forward_contract axis_frame must be {SOURCE_MESH_FRAME!r}; no "
            "alternate forward axis frame is supported"
        )

    status = forward_contract["status"]
    if status not in FORWARD_STATUSES:
        raise ValueError(
            "forward_contract status must be one of: "
            + ", ".join(FORWARD_STATUSES)
        )

    axis = forward_contract["axis"]
    # Only the axis TYPE is structural. Whether an axis is resolvable to a yaw
    # is a resolution question, reported as a blocked state rather than raised.
    if axis is not None and not isinstance(axis, str):
        raise ValueError("forward_contract axis must be a string or None")

    return status, axis


def _validate_up_alignment_status(up_alignment_status):
    if not isinstance(up_alignment_status, str):
        raise ValueError("up_alignment_status must be a string")

    return up_alignment_status


def _validate_world_zero_facing_axis(world_zero_facing_axis):
    if not isinstance(world_zero_facing_axis, str):
        raise ValueError("world_zero_facing_axis must be a string")

    return world_zero_facing_axis


def _result(
    phi_status,
    phi_rad,
    forward_status,
    forward_axis,
    forward_axis_frame,
    world_zero_facing_axis,
    reasons,
):
    return {
        "phi_status": phi_status,
        "phi_rad": phi_rad,
        "forward_status": forward_status,
        "forward_axis": forward_axis,
        "forward_axis_frame": forward_axis_frame,
        "world_zero_facing_axis": world_zero_facing_axis,
        "world_zero_facing_axis_frame": WORLD_ZERO_FACING_FRAME,
        "reasons": list(reasons),
    }


def resolve_intrinsic_yaw_phi(
    *,
    forward_contract,
    up_alignment_status,
    world_zero_facing_axis=SUPPORTED_WORLD_ZERO_FACING_AXIS,
):
    """Derive the mesh-intrinsic yaw from resolved forward metadata.

    Deterministic precondition order: contract shape and frame, then up
    alignment, then zero-facing, then the forward status, then the axis, then
    phi. A malformed frame declaration is a hard error even when the forward
    status is unresolved - malformed contracts are never hidden behind an
    ``unresolved`` state.
    """

    # 1 + 2. contract shape, frame declaration, status and axis vocabulary.
    status, axis = _validate_contract(forward_contract)

    # 3. up alignment.
    up_alignment = _validate_up_alignment_status(up_alignment_status)

    # 4. WORLD zero-facing target (never a raw-mesh axis).
    world_target = _validate_world_zero_facing_axis(world_zero_facing_axis)

    def result(phi_status, phi_rad, reasons):
        return _result(
            phi_status,
            phi_rad,
            status,
            axis,
            forward_contract["axis_frame"],
            world_target,
            reasons,
        )

    if up_alignment != UP_ALIGNMENT_VERIFIED:
        return result(PHI_STATUS_BLOCKED, None, ["up_alignment_not_verified"])

    if world_target != SUPPORTED_WORLD_ZERO_FACING_AXIS:
        return result(
            PHI_STATUS_BLOCKED, None, ["world_zero_facing_axis_unsupported"]
        )

    # 5. forward status: no forward means no phi.
    if status in FORWARD_STATUSES_WITHOUT_AXIS:
        return result(PHI_STATUS_UNRESOLVED, None, [f"forward_{status}"])

    # 6 + 7. an axis-asserting status requires a resolvable axis.
    if axis not in PHI_BY_RAW_FORWARD:
        return result(PHI_STATUS_BLOCKED, None, ["invalid_forward_axis"])

    return result(PHI_STATUS_RESOLVED, PHI_BY_RAW_FORWARD[axis], [])
