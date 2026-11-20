"""Semantic vertical circulation intelligence (ARCH-VERTICAL-02).

Derives the vertical CIRCULATION INTENT of a building from its building domain
and level configuration. It answers only "what vertical elements does this
programme intend, and what do they connect?" - never "how big is it?" and never
"where is it?".

Audit that motivated this module (see the phase report):

- the only vertical logic in KnowledgeSpaceGenerator is a ``stairs`` space that
  is dropped unless a vertical transition exists and, when kept, receives
  ``connects`` / ``vertical_connection``. There is NO elevator, ramp or car-lift
  semantics anywhere in it (elevator/ramp/car_lift all appear 0 times).
- ``ElevatorRegulationRequirementReasoningV1`` resolves elevator TRIGGERS from
  authoritative regulation evidence and produces no sizing claims, but nothing
  in the space-generation path calls it.
- the substantial ramp / vehicle-access logic lives in separate, unwired
  modules and is never consulted by the space or layout layers.
- there is no commercial public-vs-service circulation distinction and no
  mixed-use shared-core / separation decision.

This module is SEMANTIC INTENT ONLY. It deliberately does NOT:

- create geometry, coordinates, polygons, footprints or placements
- decide any dimension (width, depth, height, rise, run, slope, capacity)
- select a final vehicle access mode (ramp vs car lift stays PENDING)
- read the filesystem, use randomness, UUIDs or timestamps
- modify KnowledgeSpaceGenerator, LayoutReasoner or the spatial contract

Every emitted element declares ``geometry_status = {state: "pending"}``.
"""

from __future__ import annotations

from typing import Any, Mapping


OUTPUT_TYPE = "vertical_circulation_intelligence"
OUTPUT_VERSION = "vertical_circulation_intelligence_v2"

# Element vocabulary.
ELEMENT_TYPES = ("stair", "elevator", "ramp", "car_lift")

# Roles.
ROLE_PRIMARY = "primary_vertical_circulation"
ROLE_OPTIONAL = "optional_vertical_circulation"
ROLE_REQUIRED = "required_vertical_circulation"
ROLE_PUBLIC = "public_vertical_circulation"
ROLE_SERVICE = "service_vertical_circulation"
ROLE_SHARED_CORE = "shared_core_vertical_circulation"
ROLE_COMMERCIAL = "commercial_vertical_circulation"
ROLE_RESIDENTIAL = "residential_vertical_circulation"
ROLE_VEHICLE = "vehicle_vertical_circulation"

# Domains.
DOMAIN_RESIDENTIAL = "residential"
DOMAIN_COMMERCIAL = "commercial"
DOMAIN_MIXED_USE = "mixed_use"
DOMAIN_SITE = "site"

# Floor tokens.
FLOOR_BASEMENT = "basement"
FLOOR_GROUND = "ground_floor"
FLOOR_MEZZANINE = "mezzanine"
FLOOR_UPPER = "upper_floor"
FLOOR_SITE = "site_level"

# Programme thresholds (semantic, non-dimensional).
ELEVATOR_OPTIONAL_ABOVE_GROUND = 2
ELEVATOR_REQUIRED_ABOVE_GROUND = 3

GEOMETRY_STATE_PENDING = "pending"
GEOMETRY_REASON = "vertical_geometry_not_authorized"

VEHICLE_ACCESS_PENDING = "pending"
VEHICLE_ACCESS_CANDIDATES = ("ramp", "car_lift")

STATE_RESOLVED = "vertical_circulation_resolved"
STATE_UNRESOLVED = "vertical_circulation_unresolved"

# Roles that represent a means of egress and are therefore protected zones.
_PROTECTED_ROLES = frozenset(
    (ROLE_PRIMARY, ROLE_REQUIRED, ROLE_PUBLIC, ROLE_SHARED_CORE)
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _mapping(value, label):
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping or None")

    return dict(value)


def _count(levels, key):
    value = levels.get(key, 0)
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"levels.{key} must be an integer")
    if value < 0:
        raise ValueError(f"levels.{key} must not be negative")

    return value


def _normalised_requirements(requirements):
    if requirements is None:
        return frozenset()
    if isinstance(requirements, (str, bytes)) or not isinstance(
        requirements, (list, tuple)
    ):
        raise ValueError("requirements must be a list of strings or None")

    return frozenset(
        str(item).strip().lower() for item in requirements if item is not None
    )


def resolve_building_domain(building_type):
    """Return the vertical-circulation domain for a building type."""

    if not isinstance(building_type, str):
        raise ValueError("building_type must be a non-empty string")
    if not building_type.strip():
        raise ValueError("building_type must be a non-empty string")

    from core.architecture.knowledge.floor_aware_building_program_v1 import (
        program_domain,
    )

    domain = program_domain(building_type)
    if domain is not None:
        return domain

    if building_type == "parking":
        return DOMAIN_SITE

    # villa / residential and any other residential-flavoured typology.
    if building_type in ("villa", "residential", "apartment", "house"):
        return DOMAIN_RESIDENTIAL

    return DOMAIN_RESIDENTIAL


def served_floors(levels):
    """Return the served floor stack in ascending order."""

    levels = _mapping(levels, "levels")

    above_ground = _count(levels, "above_ground")
    basement = _count(levels, "basement")
    mezzanine = _count(levels, "mezzanine")

    floors = []
    if basement > 0:
        floors.append(FLOOR_BASEMENT)
    floors.append(FLOOR_GROUND)
    if mezzanine > 0:
        floors.append(FLOOR_MEZZANINE)
    if above_ground > 1:
        floors.append(FLOOR_UPPER)

    return floors


def _element(element_type, role, floors, domain, reasons):
    if element_type not in ELEMENT_TYPES:
        raise ValueError(
            "element type must be one of: " + ", ".join(ELEMENT_TYPES)
        )

    served = list(floors)

    return {
        "type": element_type,
        "role": role,
        "connects": [
            [served[index], served[index + 1]]
            for index in range(len(served) - 1)
        ],
        "floors": served,
        "domain": domain,
        "protected_zone": role in _PROTECTED_ROLES,
        "geometry_status": {
            "state": GEOMETRY_STATE_PENDING,
            "reason": GEOMETRY_REASON,
        },
        "reasons": list(reasons),
    }


def _semantics():
    return {
        "metadata_only": True,
        "geometry_created": False,
        "coordinates_created": False,
        "dimensions_decided": False,
        "vehicle_access_mode_decided": False,
    }


# ---------------------------------------------------------------------------
# domain-specific reasoning
# ---------------------------------------------------------------------------

def _residential_elements(floors, above_ground, requirements, reasons):
    elements = []

    if len(floors) > 1:
        elements.append(
            _element(
                "stair",
                ROLE_PRIMARY,
                floors,
                DOMAIN_RESIDENTIAL,
                ["residential_multi_level_requires_stair"],
            )
        )

    explicit_elevator = "elevator" in requirements or "lift" in requirements

    if explicit_elevator or above_ground >= ELEVATOR_REQUIRED_ABOVE_GROUND:
        elements.append(
            _element(
                "elevator",
                ROLE_REQUIRED,
                floors,
                DOMAIN_RESIDENTIAL,
                [
                    "elevator_explicitly_required"
                    if explicit_elevator
                    else "elevator_required_above_ground_threshold"
                ],
            )
        )
        reasons.append("residential_elevator_required")
    elif above_ground >= ELEVATOR_OPTIONAL_ABOVE_GROUND:
        elements.append(
            _element(
                "elevator",
                ROLE_OPTIONAL,
                floors,
                DOMAIN_RESIDENTIAL,
                ["elevator_optional_for_multi_storey_residential"],
            )
        )
        reasons.append("residential_elevator_optional")

    return elements


def _commercial_elements(floors, above_ground, reasons):
    elements = []

    if len(floors) > 1:
        elements.append(
            _element(
                "stair",
                ROLE_PUBLIC,
                floors,
                DOMAIN_COMMERCIAL,
                ["commercial_public_egress_required"],
            )
        )

        # Service circulation is only needed when a secondary level exists
        # (a mezzanine or an upper floor) - goods and staff do not share the
        # public route.
        if FLOOR_MEZZANINE in floors or FLOOR_UPPER in floors:
            elements.append(
                _element(
                    "stair",
                    ROLE_SERVICE,
                    floors,
                    DOMAIN_COMMERCIAL,
                    ["commercial_service_circulation_separated_from_public"],
                )
            )
            reasons.append("commercial_service_circulation_separated")

    if above_ground >= ELEVATOR_OPTIONAL_ABOVE_GROUND:
        elements.append(
            _element(
                "elevator",
                ROLE_PUBLIC,
                floors,
                DOMAIN_COMMERCIAL,
                ["commercial_public_elevator_optional"],
            )
        )

    return elements


def _mixed_use_elements(floors, above_ground, reasons):
    elements = []

    shared_floors = list(floors)
    commercial_floors = [
        floor
        for floor in floors
        if floor in (FLOOR_GROUND, FLOOR_MEZZANINE)
    ]
    residential_floors = [
        floor
        for floor in floors
        if floor in (FLOOR_GROUND, FLOOR_UPPER)
    ]

    if len(shared_floors) > 1:
        elements.append(
            _element(
                "stair",
                ROLE_SHARED_CORE,
                shared_floors,
                DOMAIN_MIXED_USE,
                ["mixed_use_shared_core_serves_all_floors"],
            )
        )

    if len(commercial_floors) > 1:
        elements.append(
            _element(
                "stair",
                ROLE_COMMERCIAL,
                commercial_floors,
                DOMAIN_COMMERCIAL,
                ["commercial_circulation_confined_to_commercial_floors"],
            )
        )

    if len(residential_floors) > 1:
        elements.append(
            _element(
                "stair",
                ROLE_RESIDENTIAL,
                residential_floors,
                DOMAIN_RESIDENTIAL,
                ["residential_circulation_confined_to_residential_floors"],
            )
        )

    if above_ground >= ELEVATOR_OPTIONAL_ABOVE_GROUND:
        elements.append(
            _element(
                "elevator",
                ROLE_SHARED_CORE,
                shared_floors,
                DOMAIN_MIXED_USE,
                ["mixed_use_shared_core_elevator"],
            )
        )

    reasons.append("mixed_use_shared_core_with_domain_separation")

    separation = {
        "shared_core": True,
        "separation_required": True,
        "shared_floors": shared_floors,
        "commercial_floors": commercial_floors,
        "residential_floors": residential_floors,
        # A domain that occupies a single level needs no vertical element of its
        # own; the requirement is stated explicitly so the absence is a declared
        # decision rather than an omission.
        "commercial_vertical_circulation_required": len(commercial_floors) > 1,
        "residential_vertical_circulation_required": len(residential_floors) > 1,
        "reasons": [
            "commercial_and_residential_circulation_must_be_separated",
            "shared_core_limited_to_ground_level_access",
        ],
    }

    return elements, separation


def _vehicle_elements(building_type, levels, reasons):
    """Vehicle circulation intent. The ramp/car-lift MODE stays pending."""

    levels = _mapping(levels, "levels")
    basement = _count(levels, "basement")

    is_parking = building_type == "parking"

    if not is_parking and basement == 0:
        return [], {
            "status": VEHICLE_ACCESS_PENDING,
            "mode": None,
            "candidates": list(VEHICLE_ACCESS_CANDIDATES),
            "decided": False,
            "reasons": ["no_vehicle_level_detected"],
        }

    if basement > 0:
        vehicle_floors = [FLOOR_SITE, FLOOR_BASEMENT]
        reason = "basement_parking_requires_vehicle_vertical_connection"
    else:
        vehicle_floors = [FLOOR_SITE, FLOOR_GROUND]
        reason = "parking_building_requires_vehicle_vertical_connection"

    element = _element(
        "ramp",
        ROLE_VEHICLE,
        vehicle_floors,
        DOMAIN_SITE,
        [reason, "vehicle_access_mode_decision_deferred"],
    )

    vehicle_access = {
        "status": VEHICLE_ACCESS_PENDING,
        "mode": None,
        "candidates": list(VEHICLE_ACCESS_CANDIDATES),
        "decided": False,
        "geometry_status": {
            "state": GEOMETRY_STATE_PENDING,
            "reason": "vehicle_geometry_not_authorized",
        },
        "reasons": [
            "ramp_vs_car_lift_decision_placeholder",
            "vehicle_access_mode_decision_deferred",
        ],
    }

    reasons.append("parking_ramp_reasoning_emitted")

    return [element], vehicle_access


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def resolve_vertical_circulation_intelligence(
    *,
    building_type,
    levels=None,
    requirements=None,
    vehicle_access_evidence=None,
):
    """Resolve the vertical circulation intent for one building programme.

    ``building_type`` selects the domain. ``levels`` is an OPTIONAL mapping of
    ``above_ground`` / ``basement`` / ``mezzanine`` counts. ``requirements`` is
    an OPTIONAL list of explicitly requested element names.

    Returns a metadata-only contract whose ``vertical_elements`` describe TYPE,
    ROLE, CONNECTIONS, FLOORS, DOMAIN, PROTECTED_ZONE and a PENDING
    ``geometry_status``. No dimension and no coordinate is ever produced, and
    the vehicle access mode is deliberately left PENDING.

    Malformed input raises ``ValueError``.
    """

    if not isinstance(building_type, str) or not building_type.strip():
        raise ValueError("building_type must be a non-empty string")

    resolved_levels = _mapping(levels, "levels")
    resolved_requirements = _normalised_requirements(requirements)
    evidence = _mapping(vehicle_access_evidence, "vehicle_access_evidence")

    domain = resolve_building_domain(building_type)

    floors = served_floors(resolved_levels)
    above_ground = _count(resolved_levels, "above_ground")

    reasons = []
    separation = None

    if domain == DOMAIN_MIXED_USE:
        elements, separation = _mixed_use_elements(
            floors, above_ground, reasons
        )
    elif domain == DOMAIN_COMMERCIAL:
        elements = _commercial_elements(floors, above_ground, reasons)
    else:
        elements = _residential_elements(
            floors, above_ground, resolved_requirements, reasons
        )

    vehicle_elements, vehicle_access = _vehicle_elements(
        building_type, resolved_levels, reasons
    )
    elements.extend(vehicle_elements)

    if evidence:
        # Supplied evidence is preserved verbatim as provenance; it never
        # resolves the mode in this phase.
        vehicle_access["evidence"] = evidence
        vehicle_access["reasons"].append("vehicle_access_evidence_recorded")

    if not elements:
        reasons.append("no_vertical_transition_required")

    return {
        "type": OUTPUT_TYPE,
        "version": OUTPUT_VERSION,
        "building_type": building_type,
        "building_domain": domain,
        "levels": {
            "above_ground": above_ground,
            "basement": _count(resolved_levels, "basement"),
            "mezzanine": _count(resolved_levels, "mezzanine"),
        },
        "served_floors": floors,
        "vertical_elements": elements,
        "circulation_separation": separation,
        "vehicle_access": vehicle_access,
        "semantics": _semantics(),
        "status": {
            "state": STATE_RESOLVED,
            "reasons": reasons,
        },
    }


def elements_of_type(contract, element_type):
    """Return the elements of one type from a resolved contract."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")
    if element_type not in ELEMENT_TYPES:
        raise ValueError(
            "element_type must be one of: " + ", ".join(ELEMENT_TYPES)
        )

    return [
        element
        for element in contract.get("vertical_elements", [])
        if element.get("type") == element_type
    ]


def elements_with_role(contract, role):
    """Return the elements carrying one role."""

    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")

    return [
        element
        for element in contract.get("vertical_elements", [])
        if element.get("role") == role
    ]
