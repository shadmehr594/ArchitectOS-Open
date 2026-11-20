from core.architecture.geometry.main_entrance_opening_placement_selector_v1 import (
    MainEntranceOpeningPlacementSelectorV1,
)
from core.architecture.geometry.exterior_entrance_geometry_resolver_v1 import (
    ExteriorEntranceGeometryResolverV1,
)


def _geometry(approach_line):
    footprint = [[0, 0], [10, 0], [10, 8], [0, 8]]
    entrance_footprint = [[3, 0], [7, 0], [7, 3], [3, 3]]
    opening = {
        "id": "D1", "type": "door", "category": "main_entrance",
        "floor": "F1", "space": "entrance", "width": 1.4,
        "candidate_wall_ids": ["W-bottom", "W-left"], "candidate_count": 2,
        "host_wall_id": None, "host_boundary_id": None,
        "host_resolution_status": "host_pending_multiple_candidates",
        "host_resolution_reason": "multiple_compatible_walls_require_architectural_evidence",
    }
    walls = [
        {"wall_id": "W-bottom", "floor": "F1", "spaces": ["entrance"],
         "is_exterior": True, "start": [3, 0], "end": [7, 0], "boundary_ids": ["B-bottom"]},
        {"wall_id": "W-left", "floor": "F1", "spaces": ["entrance"],
         "is_exterior": True, "start": [3, 0], "end": [3, 3], "boundary_ids": ["B-left"]},
    ]
    spaces = [{"name": "entrance", "floor": "F1", "footprint": {"points": entrance_footprint}}]
    floors = [{"floor": "F1", "footprint": {"points": footprint}}]
    site = {"pedestrian_access": {
        "id": "PA-1", "geometry_status": "resolved", "approach_line": approach_line,
    }}
    return opening, walls, spaces, floors, site


def test_resolves_unique_host_and_center_from_architectural_evidence():
    opening, walls, spaces, floors, site = _geometry([[5, -4], [5, 2]])
    result = MainEntranceOpeningPlacementSelectorV1().resolve(
        [opening], walls, spaces, floors, site
    )[0]
    assert result["host_wall_id"] == "W-bottom"
    assert result["host_boundary_id"] == "B-bottom"
    assert result["center"] == [5.0, 0.0]
    assert result["placement_access_id"] == "PA-1"
    assert result["placement_approach_line"] == [[5.0, -4.0], [5.0, 2.0]]
    assert result["host_resolution_status"] == "resolved_from_architectural_placement_evidence"
    assert result["placement_resolution_status"] == "resolved"


def test_preserves_multiple_candidate_ambiguity_when_approach_hits_corner():
    opening, walls, spaces, floors, site = _geometry([[-2, -2], [4, 4]])
    result = MainEntranceOpeningPlacementSelectorV1().resolve(
        [opening], walls, spaces, floors, site
    )[0]
    assert result["host_wall_id"] is None
    assert result.get("center") is None
    assert result["host_resolution_status"] == "host_pending_multiple_candidates"
    assert result["host_resolution_reason"] == "multiple_compatible_walls_require_architectural_evidence"
    assert result["placement_resolution_status"] == "pending"


def test_does_not_use_nearest_wall_without_resolved_site_access():
    opening, walls, spaces, floors, site = _geometry([[5, -4], [5, 2]])
    site["pedestrian_access"]["geometry_status"] = "pending"
    result = MainEntranceOpeningPlacementSelectorV1().resolve(
        [opening], walls, spaces, floors, site
    )[0]
    assert result["host_wall_id"] is None
    assert result["host_resolution_status"] == "host_pending_multiple_candidates"


def test_resolved_opening_is_threshold_source_of_truth_for_exterior_transition():
    opening, walls, spaces, floors, site = _geometry([[5, -4], [5, 2]])
    resolved_opening = MainEntranceOpeningPlacementSelectorV1().resolve(
        [opening], walls, spaces, floors, site
    )[0]
    transition = {
        "site_datum": {"elevation": 0.0},
        "finished_floor": {"level": "F1", "elevation": 0.4},
        "entrance_platform": {"elevation": 0.4, "depth": 1.2},
        "platform_rules": {"side_clearance": 0.3},
        "exterior_steps": {
            "start_z": 0.0, "end_z": 0.4, "total_rise": 0.4,
            "riser_count": 2, "riser_height": 0.2,
            "tread_count": None, "tread_depth": None,
        },
    }
    result = ExteriorEntranceGeometryResolverV1().resolve({
        "openings": [resolved_opening], "physical_walls": walls,
        "spaces": spaces, "floor_geometry": floors, "site_geometry": site,
    }, transition)
    assert result["entrance_threshold"]["center"] == [5.0, 0.0]
    assert result["entrance_threshold"]["elevation"] == 0.4
    assert result["exterior_platform_geometry"]["host_wall_id"] == "W-bottom"
    assert result["entrance_steps_geometry"]["riser_count"] == 2
    assert result["entrance_steps_geometry"]["riser_height"] == 0.2
    assert result["entrance_steps_geometry"]["geometry_status"] == "pending"
