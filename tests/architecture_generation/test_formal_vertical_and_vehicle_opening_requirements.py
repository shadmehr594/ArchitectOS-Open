import copy

from core.architecture.brain.architectural_brain import ArchitecturalBrain
from core.architecture.geometry.architectural_physical_opening_resolver_v1 import (
    ArchitecturalPhysicalOpeningResolverV1,
)
from core.architecture.geometry.vehicle_access_geometry_resolver_v1 import (
    VehicleAccessGeometryResolverV1,
)
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from tests.architecture_generation.test_complete_architecture_vehicle_access_acceptance import (
    _architectural_intent,
    _selection,
    _south_required_run,
)


def _geometry(stair_changes=None):
    intent = _architectural_intent(0)
    stair = intent["vertical_transport"]["stairs"][0]
    for key, value in (stair_changes or {}).items():
        if value is None:
            stair.pop(key, None)
        else:
            stair[key] = value
    return intent, ArchitecturalBrain().design(intent).to_dict()["architectural_intelligence"]


def test_stair_requirements_traverse_intent_reasoning_and_geometry_resolver():
    intent, intelligence = _geometry()
    stair_system = next(item for item in intelligence["vertical_systems"]["vertical_systems"]
                        if item.get("type") == "stairs")
    stair = next(item for item in intelligence["architectural_geometry"]["vertical_geometry"]
                 if item.get("type") == "stair_geometry")
    assert intent["vertical_transport"]["stairs"][0]["source"] == "project_requirement"
    assert stair_system["parameters"]["clear_width"] == 1.2
    assert stair["geometry_status"] == "resolved"
    assert stair["clear_width"] == 1.2
    assert stair["flight_count"] == 2
    assert stair["slab_opening"]["geometry_status"] == "resolved"


def test_required_stair_without_explicit_width_fails_closed():
    _, intelligence = _geometry({"clear_width": None})
    stair = next(item for item in intelligence["architectural_geometry"]["vertical_geometry"]
                 if item.get("type") == "stair_geometry")
    assert stair["geometry_status"] == "insufficient_evidence"
    assert "clear_width" in stair["missing_evidence"]


def test_required_stair_without_allowed_zone_fails_closed():
    _, intelligence = _geometry({"allowed_zone": None})
    stair = next(item for item in intelligence["architectural_geometry"]["vertical_geometry"]
                 if item.get("type") == "stair_geometry")
    assert stair["geometry_status"] == "insufficient_evidence"
    assert "authoritative_protected_core_footprint" in stair["missing_evidence"]


def test_vehicle_opening_height_traverses_project_requirement():
    _, intelligence = _geometry()
    geometry = intelligence["architectural_geometry"]
    # This test isolates the vehicle-opening requirement; parking topology is
    # covered by its own architecture-first acceptance contract.
    geometry["project_requirements"]["parking_requirements"] = []
    basement = next(slab for slab in geometry["slabs"] if slab.get("floor") == "basement")
    points = basement["footprint"]["points"]
    target = [sum(point[0] for point in points) / len(points),
              sum(point[1] for point in points) / len(points)]
    geometry["site_geometry"].update({"parking_access_points": {"basement": target},
                                      "conflict_zones": []})
    result = VehicleAccessGeometryResolverV1().resolve(
        _selection("south_road", "south", "vehicle_ramp", 0.0, _south_required_run(target)),
        geometry, {"slope": 0.15},
    )
    assert result["status"] == "resolved"
    assert result["vehicle_wall_opening"]["resolved_height"] == 2.4


def test_vehicle_opening_without_clear_height_remains_pending():
    _, intelligence = _geometry()
    geometry = intelligence["architectural_geometry"]
    geometry["project_requirements"]["vehicle_access"]["entrances"][0].pop("clear_height")
    basement = next(slab for slab in geometry["slabs"] if slab.get("floor") == "basement")
    points = basement["footprint"]["points"]
    target = [sum(point[0] for point in points) / len(points),
              sum(point[1] for point in points) / len(points)]
    geometry["site_geometry"].update({"parking_access_points": {"basement": target},
                                      "conflict_zones": []})
    result = VehicleAccessGeometryResolverV1().resolve(
        _selection("south_road", "south", "vehicle_ramp", 0.0, _south_required_run(target)),
        geometry, {"slope": 0.15},
    )
    assert result["status"] == "vehicle_wall_opening_pending"
    assert result["geometry_generation_allowed"] is False


def test_physical_opening_still_requires_unique_host():
    opening = {"id": "D", "type": "door", "width": 1.0, "height": 2.1,
               "opening_center": [5, 0], "candidate_wall_ids": ["W1", "W2"]}
    walls = [{"wall_id": "W1", "start": [0, 0], "end": [10, 0], "is_exterior": True},
             {"wall_id": "W2", "start": [0, 1], "end": [10, 1], "is_exterior": True}]
    openings, resolved_walls = ArchitecturalPhysicalOpeningResolverV1().resolve([opening], walls)
    assert openings[0]["geometry_status"] == "pending"
    assert not any(wall.get("physical_openings") for wall in resolved_walls)


def test_architectural_intent_preserves_formal_vehicle_and_stair_contracts():
    extracted = ArchitecturalIntent().extract({"prompt": "", "architectural_intent": {
        "vertical_transport": {"stairs": [{"id": "S", "required": True, "clear_width": 1.1}],
                               "elevators": [], "ramps": [], "escalators": []},
        "vehicle_access": {"entrances": [{"access_id": "V", "clear_height": 2.3}]},
    }})
    assert extracted["vertical_transport"]["stairs"][0]["clear_width"] == 1.1
    assert extracted["vehicle_access"]["entrances"][0]["clear_height"] == 2.3
