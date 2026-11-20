from core.architecture.reasoning.pedestrian_site_access_design_reasoner_v1 import (
    PedestrianSiteAccessDesignReasonerV1,
)
from core.architecture.geometry.pedestrian_access_geometry_resolver_v1 import (
    PedestrianAccessGeometryResolverV1,
)
from core.architecture.geometry.main_entrance_opening_placement_selector_v1 import (
    MainEntranceOpeningPlacementSelectorV1,
)


FLOORS = [{"floor": "F1", "footprint": {"points": [[6, 10], [14, 10], [14, 22], [6, 22]]}}]
SPACES = [{"name": "entrance", "floor": "F1", "footprint": {"points": [[9, 10], [11, 10], [11, 13], [9, 13]]}}]


def _site():
    return {
        "parcel_boundary": [[0, 0], [20, 0], [20, 30], [0, 30]],
        "parcel_edges": [{"id": "ROAD-EDGE", "edge_index": 0, "start": [0, 0], "end": [20, 0], "relation": "road", "confirmed": True}],
        "access_edge_index": "ROAD-EDGE",
        "pedestrian_access_width": 1.2,
        "setback_zones": [],
        "protected_zones": [],
        "pedestrian_conflict_zones": [],
        "vehicle_access_zones": [],
    }


def test_scenario_a_unique_access_resolves_and_selects_main_entrance_host():
    site = _site()
    design = PedestrianSiteAccessDesignReasonerV1().design(site, FLOORS, SPACES)
    assert design["selection_status"] == "selected_unique_candidate"
    assert design["selected_access"]["access_point"] == [10.0, 0.0]
    assert design["selected_access"]["approach_line"] == [[10.0, 0.0], [10.0, 10.0]]
    site["pedestrian_access_candidates"] = [design["selected_access"]]
    access = PedestrianAccessGeometryResolverV1().resolve(site, FLOORS)
    assert access["geometry_status"] == "resolved"
    site["pedestrian_access"] = access
    openings = [{
        "id": "D1", "category": "main_entrance", "floor": "F1", "space": "entrance", "width": 1.4,
        "candidate_wall_ids": ["W-front", "W-side"], "host_wall_id": None,
        "host_resolution_status": "host_pending_multiple_candidates",
        "host_resolution_reason": "multiple_compatible_walls_require_architectural_evidence",
    }]
    walls = [
        {"wall_id": "W-front", "spaces": ["entrance"], "is_exterior": True, "start": [9, 10], "end": [11, 10], "boundary_ids": ["B1"]},
        {"wall_id": "W-side", "spaces": ["entrance"], "is_exterior": True, "start": [9, 10], "end": [9, 13], "boundary_ids": ["B2"]},
    ]
    resolved = MainEntranceOpeningPlacementSelectorV1().resolve(openings, walls, SPACES, FLOORS, site)[0]
    assert resolved["host_wall_id"] == "W-front"
    assert resolved["center"] == [10.0, 10.0]


def test_scenario_b_equal_access_evidence_remains_pending_tie():
    site = _site()
    site["parcel_edges"] = [
        {"id": "ROAD-A", "start": [0, 0], "end": [20, 0], "relation": "road", "confirmed": True},
        {"id": "ROAD-B", "start": [0, 20], "end": [0, 0], "relation": "road", "confirmed": True},
    ]
    site["access_edge_index"] = None
    floors = [{"floor": "F1", "footprint": {"points": [[10, 10], [18, 10], [18, 18], [10, 18]]}}]
    spaces = [{"name": "entrance", "floor": "F1", "footprint": {"points": [[10, 10], [12, 10], [12, 12], [10, 12]]}}]
    result = PedestrianSiteAccessDesignReasonerV1().design(site, floors, spaces)
    assert result["selection_status"] == "pending_tie"
    assert result["selected_access"] is None
    assert result["geometry_status"] == "pending"


def test_scenario_c_vehicle_conflict_prevents_overlap_publication():
    site = _site()
    site["vehicle_access_zones"] = [{"polygon": [[8, 0], [12, 0], [12, 8], [8, 8]]}]
    result = PedestrianSiteAccessDesignReasonerV1().design(site, FLOORS, SPACES)
    assert result["selected_access"] is None
    assert all(item["vehicle_conflict_status"] != "clear" for item in result["candidates"])


def test_scenario_d_no_confirmed_road_edge_fails_closed():
    site = _site()
    site["parcel_edges"] = []
    site["access_edge_index"] = None
    result = PedestrianSiteAccessDesignReasonerV1().design(site, FLOORS, SPACES)
    assert result["geometry_status"] == "pending"
    assert result["selected_access"] is None
    assert "confirmed_road_access_edge" in result["unresolved_evidence"]


def test_scenario_e_protected_zone_blocks_straight_path_without_curve():
    site = _site()
    site["protected_zones"] = [{"polygon": [[8, 4], [12, 4], [12, 7], [8, 7]]}]
    result = PedestrianSiteAccessDesignReasonerV1().design(site, FLOORS, SPACES)
    assert result["selected_access"] is None
    assert result["candidates"][0]["selection_reason"] == "protected_zone_blocks_straight_approach"
    assert result["candidates"][0]["approach_line"] is None


def test_missing_conflict_inventory_is_not_treated_as_clear_site():
    site = _site()
    del site["vehicle_access_zones"]
    result = PedestrianSiteAccessDesignReasonerV1().design(site, FLOORS, SPACES)
    assert result["geometry_status"] == "pending"
    assert "vehicle_access_and_circulation_inventory" in result["unresolved_evidence"]


def test_multi_candidate_mode_regenerates_door_and_route_geometry_on_accessible_edge():
    site = _site()
    site["generate_multiple_candidates"] = True
    result = PedestrianSiteAccessDesignReasonerV1().design(site, FLOORS, SPACES)
    feasible = [x for x in result["candidates"] if x["geometry_status"] == "candidate"]
    assert len(feasible) >= 3
    assert len({tuple(x["access_point"]) for x in feasible}) >= 3
    assert len({tuple(tuple(p) for p in x["approach_line"]) for x in feasible}) >= 3
    assert all(x["access_segment"] and x["approach_end"] for x in feasible)
