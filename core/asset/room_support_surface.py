"""Room volume contract and support-surface resolution (Phase 3D-AO).

Phase 3D-AN proved that a furniture contact verdict is computable - and that
contact currently FAILS - but it could not act on that because it requires a
support-plane elevation that no part of the asset path can supply. Phase 3D-AK
established that no floor or ceiling reference exists anywhere in that path.

This module supplies the smallest contract that closes that gap:

- ``build_room_volume(...)``           -> a validated room volume contract
- ``resolve_room_support_surface(...)`` -> the support plane for one contact
  target, in exactly the shape Phase 3D-AN consumes: its ``plane.expected_z``
  is passed straight into the contact contract's ``support_plane_z`` argument.

This module is METADATA ONLY. It deliberately does NOT:

- move, snap, shift or correct any geometry, on any axis
- change any placement, transform, vertex, bound, center or scale
- authorise a geometry adjustment
- test furniture containment, collision or clearance
- insert anything into a scene, renderer, BIM or export structure
- import ``FurnitureAdapter``, ``placement_identity``,
  ``asset_scene_instance_collection``, ``furniture_unit_contract``,
  ``furniture_support_policy``, the Phase 3D-AN contact contract,
  ``raw_obj_loader``, ``mesh_transform_spec`` or ``mesh_transform_executor``
- read any OBJ file, the asset registry, or any other external data
- access the filesystem, use randomness, UUIDs, timestamps or global counters

NOTE: the Phase 3D-AN contact contract and its module are referred to here by
phase name rather than by module path. That module ships a wiring guard which
scans production sources for its own module name as a plain substring, so even a
documentation mention registers as a reference. Naming it would trip a guard
that is meant to catch real imports; the boundary is unchanged either way.

WHY THE TWO FUNCTIONS SHARE ONE MODULE
--------------------------------------
The support surface is a pure projection of the room volume's vertical extent.
Splitting them would create a second module with no independent consumer, which
contradicts the "smallest contract" mandate. The room volume itself is a
first-class artifact that the later containment phase will consume.

ALIGNMENT WITH EXISTING ARCHITECTURE CONVENTIONS (inspected read-only)
----------------------------------------------------------------------
``core/architecture/geometry/space_boundary_opening_host_graph_engine_v1.py``
defines the authoritative room-footprint record as ``space_id``, ``floor``,
``polygon: list[list[float]]``, ``area_m2``, ``perimeter_m`` - with NO
elevation. This module reuses ``space_id`` / ``floor`` / ``polygon`` verbatim so
the two representations compose, and supplies the vertical extent that the space
record does not carry.

ELEVATION PROVENANCE IS GATED, NOT ASSUMED
------------------------------------------
``core/architecture/reasoning/project_level_contract_v1.py`` resolves
``exact_levels`` only from ``EXACT_AUTHORITIES = ("HARD_REGULATION",
"PROJECT_REQUIREMENT")`` and reports ``status`` in
``resolved`` / ``conflicted`` / ``unresolved``.

``core/architecture/reasoning/contextual_level_height_and_floor_assembly_v1.py``
emits level heights as RANGE HYPOTHESES, explicitly labelled
``"status": "hypothesis_not_exact_level"``.

Therefore this module accepts a level contract ONLY when its status is
``resolved``, and refuses to turn a range hypothesis into an exact support plane.
An elevation is only ever used as a support plane when it is either explicitly
supplied by the caller or backed by a resolved exact level.

SCOPE LIMITS (deliberate)
-------------------------
No footprint area and no room volume in cubic metres are computed. Neither has a
consumer yet, and deriving them would pull polygon geometry into a phase whose
mandate is the support surface. The polygon is validated and preserved verbatim.
"""

from __future__ import annotations

import math
from typing import Any, Mapping


OUTPUT_TYPE_ROOM_VOLUME = "room_volume"
OUTPUT_VERSION_ROOM_VOLUME = "room_volume_v1"

OUTPUT_TYPE_SUPPORT_SURFACE = "room_support_surface"
OUTPUT_VERSION_SUPPORT_SURFACE = "room_support_surface_v1"

CONTACT_TARGETS = ("floor", "ceiling")

PLANE_STATUS_RESOLVED = "resolved"
PLANE_STATUS_UNRESOLVED = "unresolved"

SOURCE_EXPLICIT = "explicit_caller_elevation"
SOURCE_LEVEL_CONTRACT = "project_level_contract_exact_levels"
SOURCE_DERIVED = "derived_from_floor_and_clear_height"

LEVEL_CONTRACT_NAME = "ProjectLevelContractV1"
LEVEL_CONTRACT_STATUSES = ("resolved", "conflicted", "unresolved")

STATE_ROOM_RESOLVED = "room_volume_resolved"
STATE_ROOM_PARTIAL = "room_volume_partial"
STATE_ROOM_UNRESOLVED = "room_volume_unresolved"

STATE_SURFACE_RESOLVED = "support_surface_resolved"
STATE_SURFACE_UNRESOLVED = "support_surface_unresolved"

# ArchitectOS canonical frame (Phase 3D-G): right-handed, Z is up.
UP_AXIS = "z"
UP_AXIS_INDEX = 2

# Cross-check tolerance for a caller supplying floor, ceiling AND clear height.
_CONSISTENCY_ABS_TOL = 1e-9


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


def _non_empty_string(value, label):
    if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")

    return value


def _optional_non_empty_string(value, label):
    if value is None:
        return None

    return _non_empty_string(value, label)


def _optional_scalar(value, label):
    if value is None:
        return None

    return _finite_scalar(value, label)


def _validate_polygon(polygon):
    """Validate an optional footprint polygon. Preserved verbatim, never used
    for the support surface and never measured."""

    if polygon is None:
        return None

    if isinstance(polygon, (str, bytes)) or not isinstance(polygon, (list, tuple)):
        raise ValueError("polygon must be a list of [x, y] points or None")
    if len(polygon) < 3:
        raise ValueError("polygon must contain at least three points")

    cleaned = []
    for index, point in enumerate(polygon):
        if isinstance(point, (str, bytes)) or not isinstance(point, (list, tuple)):
            raise ValueError(f"polygon[{index}] must be an [x, y] pair")
        if len(point) != 2:
            raise ValueError(f"polygon[{index}] must be an [x, y] pair")
        cleaned.append(
            [
                _finite_scalar(point[0], f"polygon[{index}][0]"),
                _finite_scalar(point[1], f"polygon[{index}][1]"),
            ]
        )

    return cleaned


def _validate_level_contract(level_contract):
    """Validate an optional ProjectLevelContractV1 result.

    Only a ``resolved`` contract may contribute an exact elevation; a
    ``conflicted`` or ``unresolved`` one is preserved as evidence but never
    promoted to a support plane.
    """

    if level_contract is None:
        return None
    if not isinstance(level_contract, Mapping):
        raise ValueError("level_contract must be a mapping or None")

    name = level_contract.get("contract")
    if name is not None and name != LEVEL_CONTRACT_NAME:
        raise ValueError(
            f"level_contract.contract must be {LEVEL_CONTRACT_NAME!r} or absent"
        )

    status = level_contract.get("status")
    if isinstance(status, bool) or status not in LEVEL_CONTRACT_STATUSES:
        raise ValueError(
            "level_contract.status must be one of: "
            + ", ".join(LEVEL_CONTRACT_STATUSES)
        )

    exact_levels = level_contract.get("exact_levels")
    if status == "resolved":
        if not isinstance(exact_levels, Mapping):
            raise ValueError(
                "a resolved level_contract requires an exact_levels mapping"
            )
        cleaned = {}
        for level, elevation in exact_levels.items():
            cleaned[_non_empty_string(level, "level_contract level name")] = (
                _finite_scalar(elevation, f"level_contract exact_levels[{level!r}]")
            )
    else:
        cleaned = {}

    return {"status": status, "exact_levels": cleaned}


# ---------------------------------------------------------------------------
# room volume contract
# ---------------------------------------------------------------------------

def _semantics():
    """Static, declarative facts. Every geometry action stays False."""

    return {
        "metadata_only": True,
        "geometry_modified": False,
        "placement_modified": False,
        "snap_applied": False,
        "geometry_adjustment_authorized": False,
        "containment_validated": False,
    }


def _room_state(floor_plane, ceiling_plane):
    known = [
        plane["status"] == PLANE_STATUS_RESOLVED
        for plane in (floor_plane, ceiling_plane)
    ]
    if all(known):
        return STATE_ROOM_RESOLVED
    if any(known):
        return STATE_ROOM_PARTIAL

    return STATE_ROOM_UNRESOLVED


def build_room_volume(
    *,
    space_id,
    floor=None,
    polygon=None,
    floor_elevation=None,
    ceiling_elevation=None,
    clear_height=None,
    level_contract=None,
):
    """Build a validated, metadata-only room volume contract.

    ``space_id`` is required. ``floor`` and ``polygon`` follow the existing
    space-record convention (``core/architecture/geometry/
    space_boundary_opening_host_graph_engine_v1.py``) and are preserved verbatim.

    The vertical extent is resolved from, in precedence order:

    1. an explicit ``floor_elevation`` (source ``explicit_caller_elevation``);
    2. the ``floor`` name looked up in a RESOLVED ``level_contract``'s
       ``exact_levels`` (source ``project_level_contract_exact_levels``).

    The ceiling is resolved from an explicit ``ceiling_elevation``, or derived
    as ``floor_z + clear_height``. A ``conflicted`` or ``unresolved`` level
    contract never contributes an elevation - a range hypothesis is never
    promoted to an exact support plane.

    Supplying all three of ``floor_elevation``, ``ceiling_elevation`` and
    ``clear_height`` requires them to agree, and a ceiling below its floor is
    rejected. Malformed input raises ``ValueError``.
    """

    resolved_space_id = _non_empty_string(space_id, "space_id")
    resolved_floor = _optional_non_empty_string(floor, "floor")
    resolved_polygon = _validate_polygon(polygon)
    explicit_floor_z = _optional_scalar(floor_elevation, "floor_elevation")
    explicit_ceiling_z = _optional_scalar(ceiling_elevation, "ceiling_elevation")
    resolved_clear_height = _optional_scalar(clear_height, "clear_height")
    if resolved_clear_height is not None and resolved_clear_height <= 0.0:
        raise ValueError("clear_height must be strictly positive")

    levels = _validate_level_contract(level_contract)

    # --- floor plane -------------------------------------------------------
    floor_reasons = []
    if explicit_floor_z is not None:
        floor_z = explicit_floor_z
        floor_status = PLANE_STATUS_RESOLVED
        floor_source = SOURCE_EXPLICIT
        floor_reasons.append("floor_elevation_supplied_by_caller")
    elif levels is None:
        floor_z = None
        floor_status = PLANE_STATUS_UNRESOLVED
        floor_source = None
        floor_reasons.append("floor_elevation_not_supplied")
    elif levels["status"] != "resolved":
        floor_z = None
        floor_status = PLANE_STATUS_UNRESOLVED
        floor_source = None
        floor_reasons.append(
            f"level_contract_status_{levels['status']}_not_authoritative_for_elevation"
        )
    elif resolved_floor is None:
        floor_z = None
        floor_status = PLANE_STATUS_UNRESOLVED
        floor_source = None
        floor_reasons.append("floor_name_not_supplied_for_level_lookup")
    elif resolved_floor not in levels["exact_levels"]:
        floor_z = None
        floor_status = PLANE_STATUS_UNRESOLVED
        floor_source = None
        floor_reasons.append("floor_name_absent_from_exact_levels")
    else:
        floor_z = levels["exact_levels"][resolved_floor]
        floor_status = PLANE_STATUS_RESOLVED
        floor_source = SOURCE_LEVEL_CONTRACT
        floor_reasons.append("floor_elevation_from_resolved_exact_levels")

    # --- ceiling plane -----------------------------------------------------
    ceiling_reasons = []
    if explicit_ceiling_z is not None:
        ceiling_z = explicit_ceiling_z
        ceiling_status = PLANE_STATUS_RESOLVED
        ceiling_source = SOURCE_EXPLICIT
        ceiling_reasons.append("ceiling_elevation_supplied_by_caller")
    elif floor_z is not None and resolved_clear_height is not None:
        ceiling_z = floor_z + resolved_clear_height
        ceiling_status = PLANE_STATUS_RESOLVED
        ceiling_source = SOURCE_DERIVED
        ceiling_reasons.append("ceiling_derived_from_floor_and_clear_height")
    else:
        ceiling_z = None
        ceiling_status = PLANE_STATUS_UNRESOLVED
        ceiling_source = None
        ceiling_reasons.append("ceiling_elevation_not_supplied")

    # --- cross-checks ------------------------------------------------------
    if (
        floor_z is not None
        and ceiling_z is not None
        and ceiling_z < floor_z
    ):
        raise ValueError("ceiling_elevation must be >= the floor elevation")

    if (
        explicit_floor_z is not None
        and explicit_ceiling_z is not None
        and resolved_clear_height is not None
        and abs(
            (explicit_ceiling_z - explicit_floor_z) - resolved_clear_height
        )
        > _CONSISTENCY_ABS_TOL
    ):
        raise ValueError(
            "clear_height must equal ceiling_elevation - floor_elevation when "
            "all three are supplied"
        )

    derived_clear_height = (
        ceiling_z - floor_z
        if floor_z is not None and ceiling_z is not None
        else None
    )

    floor_plane = {
        "status": floor_status,
        "z": floor_z,
        "source": floor_source,
        "reasons": floor_reasons,
    }
    ceiling_plane = {
        "status": ceiling_status,
        "z": ceiling_z,
        "source": ceiling_source,
        "reasons": ceiling_reasons,
    }

    state = _room_state(floor_plane, ceiling_plane)

    return {
        "type": OUTPUT_TYPE_ROOM_VOLUME,
        "version": OUTPUT_VERSION_ROOM_VOLUME,
        "space_id": resolved_space_id,
        "floor": resolved_floor,
        "footprint": {
            "status": (
                PLANE_STATUS_RESOLVED
                if resolved_polygon is not None
                else PLANE_STATUS_UNRESOLVED
            ),
            "polygon": resolved_polygon,
            "reasons": (
                ["polygon_supplied_by_caller"]
                if resolved_polygon is not None
                else ["polygon_not_supplied"]
            ),
        },
        "vertical_extent": {
            "status": (
                PLANE_STATUS_RESOLVED
                if state == STATE_ROOM_RESOLVED
                else PLANE_STATUS_UNRESOLVED
            ),
            "axis": UP_AXIS,
            "up_axis_index": UP_AXIS_INDEX,
            "floor": floor_plane,
            "ceiling": ceiling_plane,
            "clear_height": derived_clear_height,
            "level_contract_status": (
                levels["status"] if levels is not None else None
            ),
        },
        "semantics": _semantics(),
        "status": {
            "state": state,
            "reasons": floor_reasons + ceiling_reasons,
        },
    }


# ---------------------------------------------------------------------------
# support surface resolution
# ---------------------------------------------------------------------------

def resolve_room_support_surface(room_volume, *, contact_target):
    """Project a room volume's vertical extent onto one support plane.

    ``contact_target`` must be ``"floor"`` or ``"ceiling"`` - the vocabulary
    Phase 3D-AM emits for in-scope targets. Wall / free / unresolved targets are
    out of scope and rejected here rather than silently resolved.

    The returned ``plane.expected_z`` is the exact value Phase 3D-AN consumes as
    ``support_plane_z``; it is ``None`` whenever the plane is unresolved.
    Nothing is moved, snapped or authorised. Malformed input raises
    ``ValueError``.
    """

    if not isinstance(room_volume, Mapping):
        raise ValueError("room_volume must be a mapping")
    if room_volume.get("type") != OUTPUT_TYPE_ROOM_VOLUME:
        raise ValueError(f"room_volume.type must be {OUTPUT_TYPE_ROOM_VOLUME!r}")

    if isinstance(contact_target, bool) or contact_target not in CONTACT_TARGETS:
        raise ValueError(
            "contact_target must be one of: " + ", ".join(CONTACT_TARGETS)
        )

    vertical = room_volume.get("vertical_extent")
    if not isinstance(vertical, Mapping):
        raise ValueError("room_volume.vertical_extent must be a mapping")

    plane = vertical.get(contact_target)
    if not isinstance(plane, Mapping):
        raise ValueError(
            f"room_volume.vertical_extent.{contact_target} must be a mapping"
        )

    status = plane.get("status")
    if isinstance(status, bool) or status not in (
        PLANE_STATUS_RESOLVED,
        PLANE_STATUS_UNRESOLVED,
    ):
        raise ValueError(
            f"room_volume.vertical_extent.{contact_target}.status must be "
            "'resolved' or 'unresolved'"
        )

    expected_z = plane.get("z")
    if status == PLANE_STATUS_RESOLVED:
        if expected_z is None:
            raise ValueError(
                f"a resolved {contact_target} plane requires an elevation"
            )
        expected_z = _finite_scalar(
            expected_z, f"room_volume.vertical_extent.{contact_target}.z"
        )
    else:
        expected_z = None

    resolved = status == PLANE_STATUS_RESOLVED
    reasons = list(plane.get("reasons", []))

    return {
        "type": OUTPUT_TYPE_SUPPORT_SURFACE,
        "version": OUTPUT_VERSION_SUPPORT_SURFACE,
        "space_id": room_volume.get("space_id"),
        "floor": room_volume.get("floor"),
        "contact_target": contact_target,
        "plane": {
            "axis": UP_AXIS,
            "up_axis_index": UP_AXIS_INDEX,
            "expected_z": expected_z,
            "status": status,
            "source": plane.get("source"),
            "reasons": reasons,
        },
        "semantics": _semantics(),
        "status": {
            "state": (
                STATE_SURFACE_RESOLVED if resolved else STATE_SURFACE_UNRESOLVED
            ),
            "reasons": reasons,
        },
    }
