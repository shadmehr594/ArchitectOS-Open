"""Reusable functional-space ontology for architecture-first planning.

Numeric expectations in this module are design heuristics unless an explicit
project or verified-regulation evidence record overrides them.  The ontology
contains no Parcel2 coordinates and does not generate geometry.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable


class KnowledgeProvenance(str, Enum):
    VERIFIED_REGULATION = "VERIFIED_REGULATION"
    PROJECT_CONTRACT = "PROJECT_CONTRACT"
    ARCHITECTURAL_DESIGN_HEURISTIC = "ARCHITECTURAL_DESIGN_HEURISTIC"


class Ownership(str, Enum):
    PRIVATE = "PRIVATE"
    COMMON = "COMMON"
    SHARED_ENVIRONMENTAL = "SHARED_ENVIRONMENTAL"


@dataclass(frozen=True)
class DimensionalExpectation:
    clear_width_m: float
    area_range_m2: tuple[float, float]
    aspect_ratio_range: tuple[float, float]
    usable_wall_m: float
    circulation_strip_m: float
    provenance: KnowledgeProvenance = KnowledgeProvenance.ARCHITECTURAL_DESIGN_HEURISTIC
    evidence_id: str = "ARCHITECTURAL_USE_FIT_HEURISTIC_V1"


@dataclass(frozen=True)
class SpaceType:
    semantic_class: str
    functional_role: str
    occupancy_role: str
    zone: str
    traversable: str
    requires_door: str
    may_be_open_plan: bool
    direct_access_policy: str
    allowed_neighbors: tuple[str, ...]
    forbidden_neighbors: tuple[str, ...]
    daylight: str
    privacy: str
    wet_service: bool
    furniture_zones: tuple[str, ...]
    dimensions: DimensionalExpectation
    opening_constraints: tuple[str, ...]
    ownership: Ownership
    exterior_open_to_sky: bool = False

    def to_dict(self):
        value = asdict(self)
        value["ownership"] = self.ownership.value
        value["dimensions"]["provenance"] = self.dimensions.provenance.value
        return value


def _d(width, lo, hi, ar_lo, ar_hi, wall, route):
    return DimensionalExpectation(width, (lo, hi), (ar_lo, ar_hi), wall, route)


def _s(name, role, occupancy, zone, traversable, door, open_plan, access,
       allowed, forbidden, daylight, privacy, wet, furniture, dims, openings,
       ownership=Ownership.PRIVATE, sky=False):
    return SpaceType(name, role, occupancy, zone, traversable, door, open_plan,
                     access, tuple(allowed), tuple(forbidden), daylight, privacy,
                     wet, tuple(furniture), dims, tuple(openings), ownership, sky)


CATALOG = {
    "LIVING_RECEPTION": _s("LIVING_RECEPTION", "PUBLIC_DISTRIBUTION_AND_STAY", "DOMESTIC_PUBLIC", "PUBLIC", "CONDITIONAL_FURNITURE_ROUTE", "CONDITIONAL", True, "ENTRY_OR_HALL", ("DINING", "OPEN_KITCHEN", "TERRACE_BALCONY", "PRIVATE_HALL_CORRIDOR"), ("GUEST_WC",), "DIRECT_EXTERIOR_OR_VALID_COURT", "LOW", False, ("SOFA_ZONE", "CIRCULATION_EDGE"), _d(3.2, 16, 45, .55, 1.8, 3.0, .9), ("NO_AUTOMATIC_DOOR",)),
    "DINING": _s("DINING", "EATING_AND_PUBLIC_TRANSITION", "DOMESTIC_PUBLIC", "PUBLIC", "CONDITIONAL_FURNITURE_ROUTE", "NO_IF_OPEN", True, "LIVING_OR_ENTRY", ("LIVING_RECEPTION", "OPEN_KITCHEN", "CLOSED_KITCHEN"), (), "BORROWED_IF_OPEN", "LOW", False, ("DINING_TABLE_CLEARANCE",), _d(2.7, 8, 20, .55, 1.8, 2.4, .8), ("OPEN_CONNECTION_PREFERRED",)),
    "OPEN_KITCHEN": _s("OPEN_KITCHEN", "FOOD_PREPARATION_OPEN", "DOMESTIC_SERVICE", "PUBLIC_SERVICE", "CONDITIONAL_CLEAR_PASSAGE", "NO", True, "LIVING_OR_DINING_OPEN", ("LIVING_RECEPTION", "DINING"), ("BEDROOM",), "BORROWED_OR_DIRECT", "MEDIUM", True, ("COUNTER_RUN", "APPLIANCE_ZONE", "PASSAGE"), _d(2.4, 7, 18, .45, 2.2, 2.4, 1.0), ("OPEN_CONNECTION_NO_FAKE_DOOR",)),
    "CLOSED_KITCHEN": _s("CLOSED_KITCHEN", "FOOD_PREPARATION_ENCLOSED", "DOMESTIC_SERVICE", "SERVICE", "NO", "YES", False, "PUBLIC_OR_SERVICE_TRANSITION", ("DINING", "LIVING_RECEPTION", "PRIVATE_HALL_CORRIDOR"), ("BEDROOM",), "DIRECT_OR_VALID_BORROWED", "MEDIUM", True, ("COUNTER_RUN", "APPLIANCE_ZONE", "PASSAGE"), _d(2.4, 7, 20, .45, 2.2, 2.4, 1.0), ("DOOR_CLEAR_OF_COUNTER",)),
    "BEDROOM": _s("BEDROOM", "SLEEPING", "DOMESTIC_PRIVATE", "PRIVATE", "NO", "YES", False, "CIRCULATION_OR_INTENTIONAL_PUBLIC_HALL", ("PRIVATE_HALL_CORRIDOR", "DRESSING", "ENSUITE"), ("GUEST_WC", "PARKING_BAY"), "REQUIRED_VALID_WINDOW", "HIGH", False, ("BED", "WARDROBE_WALL", "BED_CIRCULATION"), _d(2.8, 9, 18, .55, 1.8, 2.4, .7), ("DOOR_NOT_ON_BED_HEAD_WALL",)),
    "MASTER_BEDROOM_SLEEPING": _s("MASTER_BEDROOM_SLEEPING", "PRIMARY_SLEEPING", "DOMESTIC_PRIVATE", "PRIVATE", "NO", "YES", False, "PRIVATE_TRANSITION", ("DRESSING", "ENSUITE", "PRIVATE_HALL_CORRIDOR"), ("GUEST_WC",), "REQUIRED_VALID_WINDOW", "HIGH", False, ("DOUBLE_BED", "WARDROBE_WALL", "BED_CIRCULATION"), _d(3.2, 13, 24, .6, 1.7, 2.8, .75), ("PRIVACY_CONTROLLED",)),
    "DRESSING": _s("DRESSING", "CLOTHING_STORAGE_TRANSITION", "DOMESTIC_PRIVATE", "PRIVATE", "CONDITIONAL_TO_ENSUITE_ONLY", "YES", False, "MASTER_SLEEP_OR_PRIVATE_HALL", ("MASTER_BEDROOM_SLEEPING", "ENSUITE"), ("LIVING_RECEPTION",), "NONE", "HIGH", False, ("WARDROBE_RUNS", "DRESSING_PASSAGE"), _d(1.6, 3, 9, .45, 2.5, 1.8, .9), ("DOOR_CLEAR_OF_WARDROBE",)),
    "ENSUITE": _s("ENSUITE", "PRIVATE_WET_SERVICE", "DOMESTIC_PRIVATE_SERVICE", "PRIVATE_SERVICE", "NO", "YES", False, "MASTER_OR_DRESSING", ("MASTER_BEDROOM_SLEEPING", "DRESSING"), ("LIVING_RECEPTION",), "VENTILATION_REQUIRED", "VERY_HIGH", True, ("WC_FIXTURE", "BASIN", "SHOWER", "DOOR_CLEARANCE"), _d(1.5, 3.5, 8, .45, 2.4, 1.2, .6), ("NO_TRANSIT",)),
    "FAMILY_BATHROOM": _s("FAMILY_BATHROOM", "SHARED_WET_SERVICE", "DOMESTIC_PRIVATE_SERVICE", "PRIVATE_SERVICE", "NO", "YES", False, "PRIVATE_HALL", ("PRIVATE_HALL_CORRIDOR",), ("LIVING_RECEPTION",), "VENTILATION_REQUIRED", "HIGH", True, ("BATH_OR_SHOWER", "BASIN", "DOOR_CLEARANCE"), _d(1.6, 4, 9, .5, 2.2, 1.4, .6), ("NO_TRANSIT",)),
    "GUEST_WC": _s("GUEST_WC", "TOILET_SERVICE", "DOMESTIC_SERVICE", "TRANSITION_SERVICE", "NO", "YES", False, "SCREENED_TRANSITION", ("ENTRANCE_SHOE_OFF", "PRIVATE_HALL_CORRIDOR"), ("LIVING_RECEPTION", "DINING"), "VENTILATION_REQUIRED", "HIGH", True, ("WC_FIXTURE", "BASIN", "DOOR_CLEARANCE"), _d(1.1, 1.8, 4, .4, 2.8, .8, .55), ("NO_DIRECT_PUBLIC_EXPOSURE", "NO_TRANSIT")),
    "STORAGE_LINEN": _s("STORAGE_LINEN", "STORAGE", "SERVICE", "SERVICE", "NO", "YES", False, "CIRCULATION_OR_SERVICE", ("PRIVATE_HALL_CORRIDOR",), (), "NONE", "MEDIUM", False, ("SHELVING",), _d(.9, 1, 5, .3, 3.2, .8, .55), ("NO_TRANSIT_RESIDENTIAL",)),
    "ENTRANCE_SHOE_OFF": _s("ENTRANCE_SHOE_OFF", "PRIVATE_THRESHOLD", "DOMESTIC_TRANSITION", "TRANSITION", "YES", "YES_EXTERIOR", True, "COMMON_TO_PRIVATE_ENTRY", ("LIVING_RECEPTION", "PRIVATE_HALL_CORRIDOR"), ("BEDROOM",), "NONE", "MEDIUM", False, ("SHOE_STORAGE", "ENTRY_CLEARANCE"), _d(1.4, 3, 8, .45, 2.5, 1.2, .9), ("SAFE_THRESHOLD",)),
    "PRIVATE_HALL_CORRIDOR": _s("PRIVATE_HALL_CORRIDOR", "CONNECTION_DERIVED_FROM_GRAPH", "CIRCULATION", "TRANSITION", "YES", "NO_BY_DEFAULT", True, "SERVES_DESTINATIONS", ("BEDROOM", "FAMILY_BATHROOM", "STORAGE_LINEN"), (), "NONE", "MEDIUM", False, ("CLEAR_ROUTE",), _d(1.0, 2, 14, .1, 8, 0, .95), ("MINIMIZE", "NO_DEAD_END_WITHOUT_DESTINATION")),
    "COMMON_CORRIDOR_LANDING": _s("COMMON_CORRIDOR_LANDING", "COMMON_SAFE_DISTRIBUTION", "COMMON_CIRCULATION", "COMMON", "YES", "NO_BY_DEFAULT", True, "STAIR_OR_ELEVATOR", ("STAIR", "ELEVATOR_LOBBY", "ENTRANCE_SHOE_OFF"), (), "NONE", "MEDIUM", False, ("WALKABLE_LANDING", "DOOR_SWING_CLEARANCE"), _d(1.2, 4, 20, .2, 5, 0, 1.2), ("SAME_LEVEL_CONTINUITY",), Ownership.COMMON),
    "STAIR": _s("STAIR", "VERTICAL_ACCESS", "COMMON_CIRCULATION", "COMMON", "YES_VERTICAL", "CONDITIONAL", False, "REAL_LANDING_EACH_LEVEL", ("COMMON_CORRIDOR_LANDING", "ELEVATOR_LOBBY"), ("BEDROOM",), "NONE", "MEDIUM", False, ("FLIGHTS", "LANDINGS", "STAIR_VOID"), _d(2.0, 8, 30, .3, 3.5, 0, 1.0), ("NO_DOOR_TO_VOID",), Ownership.COMMON),
    "ELEVATOR_LOBBY": _s("ELEVATOR_LOBBY", "VERTICAL_ACCESS_INTERFACE", "COMMON_CIRCULATION", "COMMON", "YES", "NO", True, "COMMON_LANDING", ("STAIR", "COMMON_CORRIDOR_LANDING"), (), "NONE", "MEDIUM", False, ("CALL_ZONE", "TURNING_CLEARANCE"), _d(1.5, 3, 10, .45, 2.5, 0, 1.2), ("SAME_LEVEL_CONTINUITY",), Ownership.COMMON),
    "TERRACE_BALCONY": _s("TERRACE_BALCONY", "PRIVATE_OUTDOOR_STAY", "DOMESTIC_OUTDOOR", "PUBLIC_OUTDOOR", "NO", "YES", False, "INTENDED_ROOM", ("LIVING_RECEPTION", "MASTER_BEDROOM_SLEEPING"), (), "DIRECT", "MEDIUM", False, ("USABLE_OUTDOOR_ZONE",), _d(1.5, 4, 18, .25, 4, 1.5, .8), ("REAL_ROOM_CONNECTION",), Ownership.PRIVATE, True),
    "LIGHTWELL_COURTYARD": _s("LIGHTWELL_COURTYARD", "DAYLIGHT_AND_VENTILATION_VOID", "ENVIRONMENTAL", "COMMON_ENVIRONMENTAL", "NO_UNLESS_COURTYARD", "NO", False, "NO_INDOOR_ACCESS_REQUIRED", ("BEDROOM", "FAMILY_BATHROOM", "OPEN_KITCHEN"), (), "OPEN_TO_SKY", "SHARED", False, (), _d(1.5, 4, 40, .25, 4, 0, 0), ("WINDOW_BOUNDARY_RELATION",), Ownership.SHARED_ENVIRONMENTAL, True),
    "PARKING_BAY": _s("PARKING_BAY", "VEHICLE_STORAGE", "VEHICLE", "COMMON", "NO_PEDESTRIAN_TRANSIT", "NO", False, "VEHICLE_MANEUVER", ("VEHICLE_MANEUVER_ZONE", "SHARED_ACCESS"), (), "NONE", "LOW", False, ("VEHICLE_RECTANGLE", "DOOR_CLEARANCE"), _d(2.4, 11, 18, .35, .65, 0, 0), ("APPROACH_REQUIRED",), Ownership.COMMON),
    "VEHICLE_MANEUVER_ZONE": _s("VEHICLE_MANEUVER_ZONE", "VEHICLE_TURNING_AND_APPROACH", "VEHICLE", "COMMON", "YES_VEHICLE", "NO", True, "SOUTH_VEHICLE_ENTRY", ("PARKING_BAY", "SHARED_ACCESS"), (), "NONE", "LOW", False, ("SWEPT_CLEAR_ROUTE",), _d(3.0, 20, 100, .15, 6, 0, 3.0), ("OBSTACLE_FREE",), Ownership.COMMON),
    "SHARED_ACCESS": _s("SHARED_ACCESS", "SHARED_VEHICLE_PEDESTRIAN_ACCESS", "MIXED_ACCESS", "COMMON", "YES", "NO", True, "SOUTH_STREET", ("VEHICLE_MANEUVER_ZONE", "COMMON_CORRIDOR_LANDING"), (), "NONE", "MEDIUM", False, ("VEHICLE_ROUTE", "PEDESTRIAN_CLEAR_STRIP"), _d(3.0, 12, 80, .1, 8, 0, 1.0), ("CLEAR_GEOMETRY",), Ownership.COMMON),
    "COMMERCIAL_SHOP": _s("COMMERCIAL_SHOP", "COMMERCIAL_OCCUPANCY", "COMMERCIAL", "PUBLIC", "CONDITIONAL", "YES_EXTERIOR", True, "SOUTH_STREET", ("SHARED_ACCESS",), ("BEDROOM",), "DIRECT_EXTERIOR", "LOW", False, ("DISPLAY_SERVICE_ZONE", "CUSTOMER_CLEARANCE"), _d(3.0, 20, 120, .35, 2.8, 3.0, 1.0), ("INDEPENDENT_ENTRY",)),
    "COMMON_ROOF": _s("COMMON_ROOF", "COMMON_OPEN_ROOF", "COMMON_OUTDOOR", "COMMON", "CONDITIONAL", "CONDITIONAL", False, "ROOF_LANDING", ("COMMON_CORRIDOR_LANDING", "PENTHOUSE_SERVICE_ENCLOSURE"), (), "OPEN_TO_SKY", "COMMON", False, ("CLEAR_OPEN_ZONE",), _d(2.0, 20, 200, .1, 10, 0, 1.0), ("NO_FAKE_RESIDENTIAL_ROOM",), Ownership.COMMON, True),
    "PENTHOUSE_SERVICE_ENCLOSURE": _s("PENTHOUSE_SERVICE_ENCLOSURE", "ROOF_SERVICE_AND_VERTICAL_TERMINATION", "SERVICE", "COMMON_SERVICE", "NO", "YES", False, "ROOF_LANDING", ("COMMON_ROOF", "STAIR", "ELEVATOR_LOBBY"), (), "NONE", "MEDIUM", True, ("SERVICE_RESERVATION",), _d(2.0, 6, 30, .35, 3, 1.5, .9), ("NOT_RESIDENTIAL",), Ownership.COMMON),
}


ALIASES = {
    "HALL": "LIVING_RECEPTION", "LIVING_DINING": "LIVING_RECEPTION",
    "OPEN_KITCHEN_DINING": "OPEN_KITCHEN", "PRIVATE_ENTRY_HALL": "ENTRANCE_SHOE_OFF",
    "PRIVATE_CIRCULATION": "PRIVATE_HALL_CORRIDOR", "BATHROOM": "FAMILY_BATHROOM",
    "SEPARATE_WC": "GUEST_WC", "PRIVATE_TERRACE": "TERRACE_BALCONY",
    "LIGHTWELL": "LIGHTWELL_COURTYARD", "LIGHTWELL_OPEN_TO_SKY": "LIGHTWELL_COURTYARD",
    "COMMON_VERTICAL_CORE": "STAIR", "MASTER_DRESSING": "DRESSING", "MASTER_ENSUITE": "ENSUITE",
}


def resolve_space_type(semantic_class: str) -> SpaceType:
    key = ALIASES.get(semantic_class, semantic_class)
    if key not in CATALOG:
        raise KeyError(f"UNKNOWN_SPACE_SEMANTIC:{semantic_class}")
    return CATALOG[key]


def ontology_document(semantics: Iterable[str] | None = None) -> dict:
    keys = sorted(set(semantics or CATALOG))
    return {
        "schema": "FUNCTIONAL_SPACE_ONTOLOGY_V1",
        "numeric_policy": "HEURISTICS_ARE_NOT_REGULATIONS_AND_MUST_NOT_BE_PRESENTED_AS_SUCH",
        "space_types": {key: resolve_space_type(key).to_dict() for key in keys},
    }
