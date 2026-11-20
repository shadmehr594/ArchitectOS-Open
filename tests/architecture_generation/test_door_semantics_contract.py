from core.architecture.reasoning.opening_reasoner_v2 import OpeningReasonerV2
from core.architecture.geometry.architectural_opening_host_resolver_v1 import ArchitecturalOpeningHostResolverV1


def doors_for(name, building_type="residential"):
    result = OpeningReasonerV2().resolve(
        {"name": name, "zone": "private", "role": name},
        {"building_type": building_type, "floor": "F1"},
    )
    return [item for item in result["openings"] if item["type"] == "door"]


def test_residential_door_schedule_and_swing_directions():
    entrance = doors_for("entrance")[0]
    bedroom = doors_for("bedroom")[0]
    bathroom = doors_for("bathroom")[0]
    stair = doors_for("stairs")[0]
    roof = doors_for("roof_access")[0]
    assert (entrance["width"], entrance["swing_direction"]) == (1400, "outward")
    assert (bedroom["width"], bedroom["swing_direction"]) == (900, "inward")
    assert (bathroom["width"], bathroom["swing_direction"]) == (800, "inward")
    assert stair["swing_direction"] == "outward_egress"
    assert stair["fire_rating_minutes"] == 90
    assert roof["swing_direction"] == "outward"


def test_commercial_and_garage_doors_have_distinct_operations():
    commercial = doors_for("shop", "commercial")[0]
    garage = doors_for("garage")[0]
    assert commercial["operation"] == "automatic_sliding"
    assert commercial["glass_type"] == "tempered_safety_glass"
    assert commercial["width"] == 1800
    assert garage["operation"] == "rolling_shutter"
    assert garage["motorized"] is True
    assert garage["width"] == 3000


def test_room_door_selects_connection_from_adjacency():
    result = OpeningReasonerV2().resolve(
        {"name": "bedroom", "zone": "private", "role": "bedroom", "adjacent_to": ["bathroom", "corridor"]},
        {"building_type": "residential", "floor": "F2"},
    )
    door = next(item for item in result["openings"] if item["type"] == "door")
    assert door["connects_from"] == "bedroom"
    assert door["connects_to"] == "corridor"
    assert door["connection_status"] == "resolved_from_space_adjacency"


def test_internal_door_hosts_on_wall_shared_with_destination_space():
    opening = {
        "type": "door", "category": "bedroom_door", "floor": "F2",
        "space": "bedroom", "connects_to": "corridor", "width": 900,
    }
    walls = [
        {"wall_id": "outside", "floor": "F2", "spaces": ["bedroom"], "is_exterior": True, "start": [0, 0], "end": [4, 0]},
        {"wall_id": "bath", "floor": "F2", "spaces": ["bedroom", "bathroom"], "is_exterior": False, "start": [0, 1], "end": [4, 1]},
        {"wall_id": "hall", "floor": "F2", "spaces": ["bedroom", "corridor"], "is_exterior": False, "start": [0, 2], "end": [4, 2]},
    ]
    resolved = ArchitecturalOpeningHostResolverV1().resolve([opening], walls)[0]
    assert resolved["host_wall_id"] == "hall"
    assert resolved["host_resolution_status"] == "resolved_unique_physical_wall"
