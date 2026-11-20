"""Floor-aware Building Program Knowledge extension (ARCH-PROGRAM-01).

An ADDITIVE program layer that supplies the building domains and the floor-aware
program semantics that ``BuildingProgramKnowledge`` does not currently carry.

Audit summary that motivated this module (see the phase report):

- ``BuildingProgramKnowledge.programs`` knows 8 types: amphitheater, auditorium,
  cinema, commercial, mixed_use, parking, residential, villa.
- ``get_program`` returns EMPTY for apartment, shop, retail, office, gym and
  storage - so those building domains do not exist at all.
- base space records carry only ``name`` / ``zone`` / ``floor`` /
  ``dimensional_requirements``; the six required semantic fields
  (``space_type``, ``role``, ``floor_constraints``, ``privacy_requirements``,
  ``access_requirements``, ``architectural_intent``) are almost entirely absent.
- ``mezzanine`` appears ZERO times in the program knowledge, even though
  KnowledgeSpaceGenerator supports a mezzanine level.

This module is PURE PROGRAM KNOWLEDGE. It deliberately does NOT:

- create geometry, coordinates, polygons, elevations or placements
- touch BIM or IFC
- modify ``BuildingProgramKnowledge``, ``KnowledgeSpaceGenerator`` or
  ``LayoutReasoner``
- read the filesystem, use randomness, UUIDs or timestamps

ADDITIVE BY CONSTRUCTION
------------------------
``get_floor_aware_program`` answers ONLY for the building domains defined here
and delegates everything else to ``BuildingProgramKnowledge`` unchanged. An
existing building type therefore returns byte-identical program data, so
``generated_spaces``, ``generated_site_spaces`` and the Architectural Spatial
Contract remain compatible.
"""

from __future__ import annotations

from typing import Any, Mapping


EXTENSION_VERSION = "floor_aware_building_program_v1"

# ---------------------------------------------------------------------------
# building domains
# ---------------------------------------------------------------------------

RESIDENTIAL = "residential"
COMMERCIAL = "commercial"
MIXED_USE = "mixed_use"

BUILDING_DOMAINS = {
    RESIDENTIAL: ("villa", "apartment"),
    COMMERCIAL: ("shop", "retail", "office", "gym", "storage"),
    MIXED_USE: ("mixed_use",),
}

DOMAIN_BUILDING_FLOORS = {
    RESIDENTIAL: ("ground_floor", "upper_floor"),
    COMMERCIAL: ("ground_floor", "mezzanine", "upper_floor"),
    MIXED_USE: ("ground_floor", "upper_floor"),
}

# Storage categories - the storage domain is categorised, not a single room.
STORAGE_CATEGORIES = (
    "general_storage",
    "cold_storage",
    "archive_storage",
    "equipment_storage",
)

# Privacy vocabulary. NOTE: privacy is NOT the zone vocabulary - a space may sit
# in the "semi_public" zone while being "semi_private" in privacy terms.
PRIVACY_LEVELS = ("public", "semi_private", "private", "external")

# ---------------------------------------------------------------------------
# floor constraints (program-level declarations, NOT geometry)
#
# Mirrors the existing convention already used by BuildingProgramKnowledge for
# villa's terrace (``floor_constraints`` with ``role`` / ``height`` /
# ``allowed_zones`` / ``constraints``).
# ---------------------------------------------------------------------------

FLOOR_CONSTRAINTS = {
    "ground_floor": {
        "role": "public_access_level",
        "height": 3.6,
        "height_source": "floor_aware_building_program",
        "allowed_zones": ("public", "semi_public", "service", "circulation"),
        "constraints": {
            "requires_access": True,
            "vehicle_access_allowed": True,
        },
    },
    "upper_floor": {
        "role": "upper_level",
        "height": 3.2,
        "height_source": "floor_aware_building_program",
        "allowed_zones": ("semi_public", "private", "service", "circulation"),
        "constraints": {
            "requires_access": True,
            "requires_vertical_transport": True,
            "vehicle_access_allowed": False,
        },
    },
    "mezzanine": {
        "role": "commercial_mezzanine",
        "height": 2.4,
        "height_source": "floor_aware_building_program",
        "allowed_zones": ("semi_public", "service"),
        "constraints": {
            "requires_access": True,
            "requires_vertical_transport": True,
            "vehicle_access_allowed": False,
            "partial_floor": True,
        },
    },
}


# ---------------------------------------------------------------------------
# space builder
# ---------------------------------------------------------------------------

def _space(
    name,
    zone,
    floor,
    space_type,
    role,
    privacy_level,
    access,
    intent,
    dimensional_requirements=None,
    **extra
):
    """Build one floor-aware program space record.

    Every record carries the six required semantic fields.
    """

    if privacy_level not in PRIVACY_LEVELS:
        raise ValueError(
            f"{name}: privacy_level must be one of: " + ", ".join(PRIVACY_LEVELS)
        )

    record = {
        "name": name,
        "zone": zone,
        "floor": floor,
        "space_type": space_type,
        "role": role,
        "floor_constraints": dict(FLOOR_CONSTRAINTS[floor]),
        "privacy_requirements": {
            "level": privacy_level,
            "requires_screening": privacy_level == "private",
        },
        "access_requirements": dict(access),
        "architectural_intent": dict(intent),
        "dimensional_requirements": dict(dimensional_requirements or {}),
    }
    record.update(extra)

    return record


def _public(vehicle=False):
    return {
        "public_access": True,
        "staff_access": False,
        "vehicle_access": vehicle,
        "requires_accessible_route": True,
    }


def _staff():
    return {
        "public_access": False,
        "staff_access": True,
        "vehicle_access": False,
        "requires_accessible_route": True,
    }


def _resident():
    return {
        "public_access": False,
        "staff_access": False,
        "resident_access": True,
        "vehicle_access": False,
        "requires_accessible_route": True,
    }


def _intent(daylight="high", noise="low", placement="primary", ventilation=True):
    return {
        "daylight_priority": daylight,
        "noise_sensitivity": noise,
        "placement_priority": placement,
        "natural_ventilation": ventilation,
    }


# ---------------------------------------------------------------------------
# programs
# ---------------------------------------------------------------------------

def _apartment_program():
    return {
        "building_domain": RESIDENTIAL,
        "floor_distribution": {
            "ground_floor": ["entrance", "living", "kitchen", "corridor"],
            "upper_floor": ["bedroom", "bathroom", "corridor"],
        },
        "required_spaces": [
            _space("entrance", "public", "ground_floor", "dwelling_entrance", "primary",
                   "semi_private", _resident(), _intent(placement="entry"),
                   {"minimum_area": 4, "preferred_area": 6}),
            _space("living", "public", "ground_floor", "living_space", "primary",
                   "semi_private", _resident(), _intent(daylight="high"),
                   {"minimum_area": 18, "preferred_area": 26}),
            _space("kitchen", "service", "ground_floor", "kitchen_space", "support",
                   "semi_private", _resident(), _intent(daylight="medium", ventilation=True),
                   {"minimum_area": 7, "preferred_area": 11}),
            _space("corridor", "circulation", "ground_floor", "circulation_space", "circulation",
                   "semi_private", _resident(), _intent(daylight="low", placement="connector"),
                   {"minimum_area": 3, "preferred_area": 5}),
            _space("bedroom", "private", "upper_floor", "bedroom_space", "primary",
                   "private", _resident(), _intent(daylight="high", noise="high"),
                   {"minimum_area": 12, "preferred_area": 16}),
            _space("bathroom", "private", "upper_floor", "wet_space", "support",
                   "private", _resident(), _intent(daylight="low", ventilation=True),
                   {"minimum_area": 4, "preferred_area": 6}),
            _space("corridor", "circulation", "upper_floor", "circulation_space", "circulation",
                   "semi_private", _resident(), _intent(daylight="low", placement="connector"),
                   {"minimum_area": 3, "preferred_area": 5}),
        ],
        "optional_spaces": [
            _space("balcony", "external", "upper_floor", "balcony_space", "support",
                   "private", _resident(), _intent(daylight="high"),
                   {"minimum_area": 3, "preferred_area": 5}),
            _space("storage", "service", "ground_floor", "storage_space", "support",
                   "private", _resident(), _intent(daylight="low", placement="secondary"),
                   {"minimum_area": 2, "preferred_area": 4},
                   storage_category="general_storage"),
        ],
        "relationships": [
            {"from": "entrance", "to": "corridor", "type": "direct_connection"},
            {"from": "corridor", "to": "living", "type": "direct_connection"},
            {"from": "living", "to": "kitchen", "type": "adjacent"},
            {"from": "corridor", "to": "bedroom", "type": "private_connection"},
            {"from": "bedroom", "to": "bathroom", "type": "private_connection"},
        ],
    }


def _shop_program():
    return {
        "building_domain": COMMERCIAL,
        "floor_distribution": {
            "ground_floor": ["shopfront", "retail_floor", "storage", "staff_wc", "service_corridor"],
            "mezzanine": ["mezzanine"],
        },
        "required_spaces": [
            _space("shopfront", "public", "ground_floor", "shopfront_space", "primary",
                   "public", _public(), _intent(daylight="medium", placement="street_facing"),
                   {"minimum_area": 6, "preferred_area": 10}),
            _space("retail_floor", "public", "ground_floor", "retail_space", "primary",
                   "public", _public(), _intent(daylight="high"),
                   {"minimum_area": 40, "preferred_area": 80}),
            _space("storage", "service", "ground_floor", "storage_space", "support",
                   "private", _staff(), _intent(daylight="low", placement="secondary"),
                   {"minimum_area": 8, "preferred_area": 14},
                   storage_category="general_storage"),
            _space("staff_wc", "service", "ground_floor", "wet_space", "support",
                   "private", _staff(), _intent(daylight="low"),
                   {"minimum_area": 3, "preferred_area": 4}),
            _space("service_corridor", "circulation", "ground_floor", "circulation_space", "circulation",
                   "semi_private", _staff(), _intent(daylight="low", placement="connector"),
                   {"minimum_area": 3, "preferred_area": 5}),
        ],
        "optional_spaces": [
            _space("mezzanine", "semi_public", "mezzanine", "commercial_mezzanine_space", "support",
                   "semi_private", _public(), _intent(daylight="medium", placement="secondary"),
                   {"minimum_area": 12, "preferred_area": 24}),
        ],
        "relationships": [
            {"from": "shopfront", "to": "retail_floor", "type": "direct_connection"},
            {"from": "retail_floor", "to": "service_corridor", "type": "adjacent"},
            {"from": "service_corridor", "to": "storage", "type": "service_connection"},
            {"from": "retail_floor", "to": "mezzanine", "type": "vertical_connection"},
        ],
    }


def _retail_program():
    return {
        "building_domain": COMMERCIAL,
        "floor_distribution": {
            "ground_floor": ["entrance", "retail_area", "checkout", "storage", "staff_wc"],
            "mezzanine": ["mezzanine"],
        },
        "required_spaces": [
            _space("entrance", "public", "ground_floor", "retail_entrance", "primary",
                   "public", _public(), _intent(placement="entry"),
                   {"minimum_area": 5, "preferred_area": 8}),
            _space("retail_area", "public", "ground_floor", "retail_space", "primary",
                   "public", _public(), _intent(daylight="high"),
                   {"minimum_area": 50, "preferred_area": 120}),
            _space("checkout", "public", "ground_floor", "checkout_zone", "support",
                   "public", _public(), _intent(placement="exit_facing"),
                   {"minimum_area": 6, "preferred_area": 10}),
            _space("storage", "service", "ground_floor", "storage_space", "support",
                   "private", _staff(), _intent(daylight="low", placement="secondary"),
                   {"minimum_area": 10, "preferred_area": 18},
                   storage_category="general_storage"),
            _space("staff_wc", "service", "ground_floor", "wet_space", "support",
                   "private", _staff(), _intent(daylight="low"),
                   {"minimum_area": 3, "preferred_area": 4}),
        ],
        "optional_spaces": [
            _space("mezzanine", "semi_public", "mezzanine", "commercial_mezzanine_space", "support",
                   "semi_private", _public(), _intent(daylight="medium", placement="secondary"),
                   {"minimum_area": 15, "preferred_area": 30}),
        ],
        "relationships": [
            {"from": "entrance", "to": "retail_area", "type": "direct_connection"},
            {"from": "retail_area", "to": "checkout", "type": "adjacent"},
            {"from": "retail_area", "to": "storage", "type": "service_connection"},
            {"from": "retail_area", "to": "mezzanine", "type": "vertical_connection"},
        ],
    }


def _office_program():
    return {
        "building_domain": COMMERCIAL,
        "floor_distribution": {
            "ground_floor": ["reception", "open_office", "meeting_room", "staff_wc", "corridor"],
            "upper_floor": ["office_upper"],
            "mezzanine": ["mezzanine"],
        },
        "required_spaces": [
            _space("reception", "public", "ground_floor", "reception_space", "primary",
                   "public", _public(), _intent(daylight="medium", placement="entry"),
                   {"minimum_area": 12, "preferred_area": 20}),
            _space("open_office", "semi_public", "ground_floor", "office_space", "primary",
                   "semi_private", _staff(), _intent(daylight="high", noise="medium"),
                   {"minimum_area": 40, "preferred_area": 90}),
            _space("meeting_room", "semi_public", "ground_floor", "meeting_space", "support",
                   "semi_private", _staff(), _intent(daylight="medium", noise="high"),
                   {"minimum_area": 10, "preferred_area": 18}),
            _space("staff_wc", "service", "ground_floor", "wet_space", "support",
                   "private", _staff(), _intent(daylight="low"),
                   {"minimum_area": 4, "preferred_area": 6}),
            _space("corridor", "circulation", "ground_floor", "circulation_space", "circulation",
                   "semi_private", _staff(), _intent(daylight="low", placement="connector"),
                   {"minimum_area": 4, "preferred_area": 7}),
            _space("office_upper", "semi_public", "upper_floor", "office_space", "primary",
                   "semi_private", _staff(), _intent(daylight="high", noise="medium"),
                   {"minimum_area": 40, "preferred_area": 90}),
        ],
        "optional_spaces": [
            _space("mezzanine", "semi_public", "mezzanine", "commercial_mezzanine_space", "support",
                   "semi_private", _staff(), _intent(daylight="medium", placement="secondary"),
                   {"minimum_area": 12, "preferred_area": 24}),
            _space("storage", "service", "ground_floor", "storage_space", "support",
                   "private", _staff(), _intent(daylight="low", placement="secondary"),
                   {"minimum_area": 4, "preferred_area": 8},
                   storage_category="archive_storage"),
        ],
        "relationships": [
            {"from": "reception", "to": "corridor", "type": "direct_connection"},
            {"from": "corridor", "to": "open_office", "type": "direct_connection"},
            {"from": "open_office", "to": "meeting_room", "type": "adjacent"},
            {"from": "corridor", "to": "staff_wc", "type": "adjacent"},
            {"from": "open_office", "to": "office_upper", "type": "vertical_connection"},
        ],
    }


def _gym_program():
    return {
        "building_domain": COMMERCIAL,
        "floor_distribution": {
            "ground_floor": ["reception", "gym_hall", "changing_room", "wc", "storage"],
            "upper_floor": ["studio"],
            "mezzanine": ["mezzanine"],
        },
        "required_spaces": [
            _space("reception", "public", "ground_floor", "reception_space", "primary",
                   "public", _public(), _intent(daylight="medium", placement="entry"),
                   {"minimum_area": 10, "preferred_area": 18}),
            _space("gym_hall", "semi_public", "ground_floor", "gym_hall_space", "primary",
                   "semi_private", _public(), _intent(daylight="high", ventilation=True),
                   {"minimum_area": 60, "preferred_area": 140}),
            _space("changing_room", "service", "ground_floor", "changing_space", "support",
                   "private", _public(), _intent(daylight="low", ventilation=True),
                   {"minimum_area": 12, "preferred_area": 20}),
            _space("wc", "service", "ground_floor", "wet_space", "support",
                   "private", _public(), _intent(daylight="low"),
                   {"minimum_area": 4, "preferred_area": 6}),
            _space("storage", "service", "ground_floor", "storage_space", "support",
                   "private", _staff(), _intent(daylight="low", placement="secondary"),
                   {"minimum_area": 6, "preferred_area": 12},
                   storage_category="equipment_storage"),
        ],
        "optional_spaces": [
            _space("mezzanine", "semi_public", "mezzanine", "commercial_mezzanine_space", "support",
                   "semi_private", _public(), _intent(daylight="medium", placement="secondary"),
                   {"minimum_area": 20, "preferred_area": 40}),
            _space("studio", "semi_public", "upper_floor", "studio_space", "support",
                   "semi_private", _public(), _intent(daylight="high", noise="high"),
                   {"minimum_area": 30, "preferred_area": 60}),
        ],
        "relationships": [
            {"from": "reception", "to": "gym_hall", "type": "direct_connection"},
            {"from": "gym_hall", "to": "changing_room", "type": "adjacent"},
            {"from": "gym_hall", "to": "wc", "type": "adjacent"},
            {"from": "gym_hall", "to": "storage", "type": "service_connection"},
            {"from": "gym_hall", "to": "mezzanine", "type": "vertical_connection"},
        ],
    }


def _storage_program():
    return {
        "building_domain": COMMERCIAL,
        "floor_distribution": {
            "ground_floor": ["storage_hall", "loading_bay", "office", "wc"],
            "mezzanine": ["mezzanine"],
        },
        "required_spaces": [
            _space("storage_hall", "service", "ground_floor", "storage_space", "primary",
                   "private", _staff(), _intent(daylight="low", placement="primary"),
                   {"minimum_area": 80, "preferred_area": 200},
                   storage_category="general_storage"),
            _space("loading_bay", "service", "ground_floor", "loading_space", "support",
                   "private",
                   {"public_access": False, "staff_access": True, "vehicle_access": True,
                    "requires_accessible_route": True},
                   _intent(daylight="low", placement="vehicle_edge"),
                   {"minimum_area": 30, "preferred_area": 60}),
            _space("office", "semi_public", "ground_floor", "office_space", "support",
                   "semi_private", _staff(), _intent(daylight="medium"),
                   {"minimum_area": 10, "preferred_area": 16}),
            _space("wc", "service", "ground_floor", "wet_space", "support",
                   "private", _staff(), _intent(daylight="low"),
                   {"minimum_area": 3, "preferred_area": 4}),
        ],
        "optional_spaces": [
            _space("mezzanine", "service", "mezzanine", "commercial_mezzanine_space", "support",
                   "private", _staff(), _intent(daylight="low", placement="secondary"),
                   {"minimum_area": 15, "preferred_area": 30}),
        ],
        "relationships": [
            {"from": "loading_bay", "to": "storage_hall", "type": "service_connection"},
            {"from": "storage_hall", "to": "office", "type": "adjacent"},
            {"from": "office", "to": "wc", "type": "adjacent"},
            {"from": "storage_hall", "to": "mezzanine", "type": "vertical_connection"},
        ],
    }


# ---------------------------------------------------------------------------
# the extended, floor-aware program set
# ---------------------------------------------------------------------------

FLOOR_AWARE_PROGRAMS = {
    "apartment": _apartment_program(),
    "shop": _shop_program(),
    "retail": _retail_program(),
    "office": _office_program(),
    "gym": _gym_program(),
    "storage": _storage_program(),
}


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def is_floor_aware_type(building_type):
    """True when this module owns the program for ``building_type``."""

    return isinstance(building_type, str) and building_type in FLOOR_AWARE_PROGRAMS


def program_domain(building_type):
    """Return the building domain for a type, or None if unknown."""

    if not isinstance(building_type, str):
        return None

    for domain, types in BUILDING_DOMAINS.items():
        if building_type in types:
            return domain

    return None


def building_types_for_domain(domain):
    """Return the building types in a domain, or an empty tuple."""

    return tuple(BUILDING_DOMAINS.get(domain, ()))


def get_floor_aware_program(building_type, functions=None):
    """Return the program for ``building_type``.

    The floor-aware extension answers ONLY for the domains it defines. Every
    other building type is delegated to ``BuildingProgramKnowledge`` unchanged,
    so existing programs stay byte-identical.
    """

    if is_floor_aware_type(building_type):
        # Deep-copied so a caller can never mutate the program table.
        from copy import deepcopy

        return deepcopy(FLOOR_AWARE_PROGRAMS[building_type])

    from core.architecture.knowledge.building_program_knowledge import (
        BuildingProgramKnowledge,
    )

    return BuildingProgramKnowledge().get_program(building_type, functions)


def floor_distribution(program):
    """Return ``{floor: [space_name, ...]}`` for a program, order preserved."""

    if not isinstance(program, Mapping):
        raise ValueError("program must be a mapping")

    distribution = {}
    for bucket in ("required_spaces", "optional_spaces"):
        spaces = program.get(bucket, []) or []
        if not isinstance(spaces, (list, tuple)):
            raise ValueError(f"program {bucket} must be a list")

        for space in spaces:
            if not isinstance(space, Mapping):
                continue
            floor = space.get("floor")
            name = space.get("name")
            if not floor or not name:
                continue
            distribution.setdefault(floor, [])
            if name not in distribution[floor]:
                distribution[floor].append(name)

    return distribution


def spaces_on_floor(program, floor):
    """Return the required+optional spaces declared on ``floor``."""

    if not isinstance(program, Mapping):
        raise ValueError("program must be a mapping")

    selected = []
    for bucket in ("required_spaces", "optional_spaces"):
        for space in program.get(bucket, []) or []:
            if isinstance(space, Mapping) and space.get("floor") == floor:
                selected.append(space)

    return selected


def site_spaces(program):
    """Return the site-level spaces of a program (floor == "site_level").

    Kept here so a floor-aware program composes with the site contract without
    importing it.
    """

    return spaces_on_floor(program, "site_level")


def mezzanine_spaces(program):
    """Return the mezzanine spaces of a program."""

    return spaces_on_floor(program, "mezzanine")
