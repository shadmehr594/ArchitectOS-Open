"""Semantic floor / ceiling contact resolution (Phase 3D-AN).

Consumes the Phase 3D-AL unit-contract verdict and the Phase 3D-AM support-policy
result and resolves the SEMANTIC contact state of one furniture asset:

- the support target (``floor`` / ``ceiling`` / ``unresolved``)
- the expected contact plane (its axis and elevation)
- the asset's bottom / top contact coordinates
- a contact status of ``resolved`` / ``unresolved`` / ``mismatch``

This module is METADATA ONLY. It deliberately does NOT:

- snap, shift or correct geometry, on any axis, towards any surface
- modify vertices, bounds, centers or scale
- modify, recompose or apply any transform
- authorise a geometry adjustment (``geometry_adjustment_authorized`` is always
  ``False``, at every status)
- create or insert a floor, ceiling or slab into a scene
- validate collision, clearance or room containment
- import ``FurnitureAdapter``, ``furniture_unit_contract``,
  ``furniture_support_policy``, ``raw_obj_loader``, ``mesh_transform_spec`` or
  ``mesh_transform_executor`` - the two upstream contracts are consumed as
  caller-supplied MAPPINGS, which keeps this module standalone
- read any OBJ file, the asset registry, or any other external data
- access the filesystem, use randomness, UUIDs, timestamps or global counters

CONTACT MODEL
-------------
The ArchitectOS canonical world frame is Z-up (established in Phase 3D-G), so the
support surface is horizontal and the governing coordinate is ``z``:

    floor-supported  -> contact coordinate = asset bottom z = bounds.min_xyz[2]
                        offset = bottom_z - expected_plane_z
    ceiling-supported-> contact coordinate = asset top z = bounds.max_xyz[2]
                        offset = top_z - expected_plane_z

``offset`` is a MEASUREMENT of the discrepancy, never an authorisation to fix it.
It is positive when the contact coordinate sits above the expected plane and
negative when it sits below it.

Status vocabulary:

- ``resolved``   - the contact coordinate is determined AND lies within tolerance
                   of the expected plane (the asset rests on its support).
- ``mismatch``   - the contact coordinate is determined AND lies outside
                   tolerance (the asset floats above, sinks below, or is offset
                   from its support surface).
- ``unresolved`` - the contact state cannot be determined: unknown support
                   target, unusable unit confidence, no expected plane, or no
                   asset bounds.

WHY THE UNIT CONTRACT MATTERS HERE
----------------------------------
Every quantity above is a LENGTH COMPARISON. Phase 3D-AL established that both
DiffuScene and 3D-FUTURE units are only SUPPORTED, not proven. A contact verdict
computed from an ``unresolved`` unit contract would be meaningless, so an
unresolved unit contract forces ``contact.status = "unresolved"`` rather than
producing a confident-looking mismatch.

WHAT THIS MODULE DOES NOT DECIDE
--------------------------------
The expected contact plane elevation is CALLER-SUPPLIED. Phase 3D-AK established
that no floor or ceiling reference exists anywhere in the asset path, so this
module never invents one, never derives it from the asset geometry, and never
reads it from the filesystem.

The upstream contracts are NOT modified: their own
``physical_validation.contact_check_status`` stays exactly as they emitted it.
"""

from __future__ import annotations

import math
from typing import Any, Mapping


OUTPUT_TYPE = "furniture_contact_state"
OUTPUT_VERSION = "furniture_contact_state_v1"

EXPECTED_UNIT_CONTRACT_TYPE = "furniture_unit_contract"
EXPECTED_SUPPORT_POLICY_TYPE = "furniture_support_policy"

UNIT_COMPATIBILITY_STATUSES = ("proven", "supported", "unresolved")
SUPPORT_STATUSES = ("resolved", "unresolved")
SUPPORT_MODES = ("floor", "ceiling", "wall", "free")

# Only these support targets are in scope for contact resolution in this phase.
CONTACT_TARGETS = ("floor", "ceiling")

# ArchitectOS canonical frame (Phase 3D-G): right-handed, Z is up.
UP_AXIS = "z"
UP_AXIS_INDEX = 2

CONTACT_STATUS_RESOLVED = "resolved"
CONTACT_STATUS_UNRESOLVED = "unresolved"
CONTACT_STATUS_MISMATCH = "mismatch"

PLANE_STATUS_RESOLVED = "resolved"
PLANE_STATUS_UNRESOLVED = "unresolved"

STATE_RESOLVED = "contact_resolved"
STATE_MISMATCH = "contact_mismatch"
STATE_UNRESOLVED = "contact_unresolved"

# Diagnostic resting tolerance, in metres. A few millimetres is a reasonable
# "rests on the support" band for furniture; it is a DIAGNOSTIC threshold, not a
# regulation or a verified project tolerance. Override per call when a project
# tolerance is available.
DEFAULT_CONTACT_TOLERANCE_M = 0.005


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


def _optional_non_empty_string(value, label):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string or None")

    return value


def _validate_unit_contract(contract):
    """Validate the consumed Phase 3D-AL contract. Returns a compact view."""

    if not isinstance(contract, Mapping):
        raise ValueError("unit_contract must be a mapping")
    if contract.get("type") != EXPECTED_UNIT_CONTRACT_TYPE:
        raise ValueError(
            f"unit_contract.type must be {EXPECTED_UNIT_CONTRACT_TYPE!r}"
        )

    compatibility = contract.get("compatibility")
    if not isinstance(compatibility, Mapping):
        raise ValueError("unit_contract.compatibility must be a mapping")

    status = compatibility.get("status")
    if isinstance(status, bool) or status not in UNIT_COMPATIBILITY_STATUSES:
        raise ValueError(
            "unit_contract.compatibility.status must be one of: "
            + ", ".join(UNIT_COMPATIBILITY_STATUSES)
        )

    return {"compatibility_status": status}


def _validate_support_policy(policy):
    """Validate the consumed Phase 3D-AM result. Returns a compact view."""

    if not isinstance(policy, Mapping):
        raise ValueError("support_policy must be a mapping")
    if policy.get("type") != EXPECTED_SUPPORT_POLICY_TYPE:
        raise ValueError(
            f"support_policy.type must be {EXPECTED_SUPPORT_POLICY_TYPE!r}"
        )

    support = policy.get("support")
    if not isinstance(support, Mapping):
        raise ValueError("support_policy.support must be a mapping")

    status = support.get("status")
    if isinstance(status, bool) or status not in SUPPORT_STATUSES:
        raise ValueError(
            "support_policy.support.status must be one of: "
            + ", ".join(SUPPORT_STATUSES)
        )

    mode = support.get("mode")
    if status == "resolved":
        if isinstance(mode, bool) or mode not in SUPPORT_MODES:
            raise ValueError(
                "a resolved support_policy requires support.mode in: "
                + ", ".join(SUPPORT_MODES)
            )
    elif mode is not None:
        raise ValueError(
            "an unresolved support_policy requires support.mode to be None"
        )

    return {
        "status": status,
        "mode": mode,
        "rule_id": _optional_non_empty_string(
            support.get("rule_id"), "support_policy.support.rule_id"
        ),
        "category": _optional_non_empty_string(
            policy.get("category"), "support_policy.category"
        ),
    }


def _validate_bounds(bounds):
    """Validate an optional world-space AABB. Returns a NEW mapping or None."""

    if bounds is None:
        return None
    if not isinstance(bounds, Mapping):
        raise ValueError("bounds must be a mapping or None")

    minimum = _finite_vector3(bounds.get("min_xyz"), "bounds.min_xyz")
    maximum = _finite_vector3(bounds.get("max_xyz"), "bounds.max_xyz")

    for index in range(3):
        if maximum[index] < minimum[index]:
            raise ValueError("bounds.max_xyz must be >= bounds.min_xyz")

    return {"min_xyz": minimum, "max_xyz": maximum}


def _validate_plane(support_plane_z):
    """Validate the optional caller-supplied expected contact plane elevation."""

    if support_plane_z is None:
        return None

    return _finite_scalar(support_plane_z, "support_plane_z")


def _validate_tolerance(tolerance):
    if tolerance is None:
        return DEFAULT_CONTACT_TOLERANCE_M

    number = _finite_scalar(tolerance, "tolerance")
    if number < 0.0:
        raise ValueError("tolerance must be non-negative")

    return number


def _semantics():
    """Static, declarative facts. Every geometry action stays False."""

    return {
        "metadata_only": True,
        "geometry_modified": False,
        "transform_modified": False,
        "geometry_adjustment_authorized": False,
        "snap_applied": False,
    }


def _contract_state(contact_status):
    if contact_status == CONTACT_STATUS_RESOLVED:
        return STATE_RESOLVED
    if contact_status == CONTACT_STATUS_MISMATCH:
        return STATE_MISMATCH

    return STATE_UNRESOLVED


def _dedupe(values):
    seen = []
    for value in values:
        if value not in seen:
            seen.append(value)

    return seen


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def resolve_furniture_contact_state(
    *,
    unit_contract,
    support_policy,
    bounds=None,
    support_plane_z=None,
    tolerance=None,
):
    """Resolve the semantic contact state of one furniture asset.

    ``unit_contract`` is a Phase 3D-AL ``furniture_unit_contract`` mapping and
    ``support_policy`` is a Phase 3D-AM ``furniture_support_policy`` mapping.
    Both are validated and consumed read-only - neither is modified, and this
    module never imports the modules that produced them.

    ``bounds`` is an OPTIONAL world-space AABB mapping (``min_xyz`` / ``max_xyz``,
    e.g. an ``asset_scene_instance`` bounds block). ``support_plane_z`` is the
    OPTIONAL caller-supplied elevation of the expected support surface - the floor
    plane for a floor-supported asset, the ceiling plane for a ceiling-supported
    one. ``tolerance`` is an OPTIONAL non-negative resting tolerance in metres.

    Returns a metadata-only ``furniture_contact_state`` mapping whose
    ``contact.status`` is ``resolved``, ``mismatch`` or ``unresolved``.
    ``geometry_adjustment_authorized`` is always ``False`` and no coordinate is
    ever moved. Malformed input raises ``ValueError``.
    """

    unit = _validate_unit_contract(unit_contract)
    policy = _validate_support_policy(support_policy)
    box = _validate_bounds(bounds)
    plane_z = _validate_plane(support_plane_z)
    resting_tolerance = _validate_tolerance(tolerance)

    unit_usable = unit["compatibility_status"] != "unresolved"

    # --- support target ----------------------------------------------------
    policy_resolved = policy["status"] == "resolved"
    mode = policy["mode"]
    in_scope = policy_resolved and mode in CONTACT_TARGETS
    target = mode if in_scope else None

    support_block = {
        "target": target,
        "status": "resolved" if in_scope else "unresolved",
        "mode": mode,
        "rule_id": policy["rule_id"],
        "category": policy["category"],
    }

    # --- expected contact plane -------------------------------------------
    plane_reasons = []
    if target is None:
        expected_z = None
        plane_status = PLANE_STATUS_UNRESOLVED
        plane_reasons.append("support_target_unresolved")
    elif plane_z is None:
        expected_z = None
        plane_status = PLANE_STATUS_UNRESOLVED
        plane_reasons.append("support_plane_elevation_not_supplied")
    else:
        expected_z = plane_z
        plane_status = PLANE_STATUS_RESOLVED
        plane_reasons.append("support_plane_supplied_by_caller")

    # --- bottom / top contact calculation ---------------------------------
    bottom_z = box["min_xyz"][UP_AXIS_INDEX] if box is not None else None
    top_z = box["max_xyz"][UP_AXIS_INDEX] if box is not None else None

    contact_reasons = []
    contact_z = None
    offset = None
    within_tolerance = None

    if target is None:
        contact_status = CONTACT_STATUS_UNRESOLVED
        if policy_resolved and mode not in CONTACT_TARGETS:
            contact_reasons.append("support_target_out_of_scope_for_contact")
        else:
            contact_reasons.append("support_target_unresolved")
    elif not unit_usable:
        contact_status = CONTACT_STATUS_UNRESOLVED
        contact_reasons.append(
            "unit_contract_not_usable_for_length_comparison"
        )
    elif expected_z is None:
        contact_status = CONTACT_STATUS_UNRESOLVED
        contact_reasons.append("expected_contact_plane_unresolved")
    elif box is None:
        contact_status = CONTACT_STATUS_UNRESOLVED
        contact_reasons.append("asset_bounds_not_supplied")
    else:
        contact_z = bottom_z if target == "floor" else top_z
        offset = contact_z - expected_z
        within_tolerance = abs(offset) <= resting_tolerance
        if within_tolerance:
            contact_status = CONTACT_STATUS_RESOLVED
            contact_reasons.append("contact_coordinate_within_tolerance")
        else:
            contact_status = CONTACT_STATUS_MISMATCH
            contact_reasons.append("contact_coordinate_outside_tolerance")

    return {
        "type": OUTPUT_TYPE,
        "version": OUTPUT_VERSION,
        "support": support_block,
        "unit": {
            "contract_type": EXPECTED_UNIT_CONTRACT_TYPE,
            "compatibility_status": unit["compatibility_status"],
            "usable_for_contact": unit_usable,
        },
        "contact_plane": {
            "axis": UP_AXIS,
            "up_axis_index": UP_AXIS_INDEX,
            "expected_z": expected_z,
            "status": plane_status,
            "reasons": plane_reasons,
        },
        "contact": {
            "status": contact_status,
            "asset_bottom_z": bottom_z,
            "asset_top_z": top_z,
            "contact_coordinate_z": contact_z,
            "offset": offset,
            "tolerance": resting_tolerance,
            "within_tolerance": within_tolerance,
            "reasons": contact_reasons,
        },
        "semantics": _semantics(),
        "status": {
            "state": _contract_state(contact_status),
            "reasons": _dedupe(plane_reasons + contact_reasons),
        },
    }
