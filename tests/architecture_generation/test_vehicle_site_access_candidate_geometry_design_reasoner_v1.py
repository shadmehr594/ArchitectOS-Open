from core.architecture.reasoning.vehicle_site_access_candidate_geometry_design_reasoner_v1 import (
    VehicleSiteAccessCandidateGeometryDesignReasonerV1,
)
from core.architecture.reasoning.site_access_coordination_reasoner_v1 import (
    SiteAccessCoordinationReasonerV1,
)
from core.intelligence.vehicle_access_candidate_selector import VehicleAccessCandidateSelector
from core.architecture.geometry.vehicle_access_geometry_resolver_v1 import VehicleAccessGeometryResolverV1


def _site():
    return {
        "parcel_boundary": [[0, 0], [20, 0], [20, 30], [0, 30]],
        "parcel_edges": [{
            "id": "E0", "access_id": "V0", "edge_index": 0,
            "start": [0, 0], "end": [20, 0], "confirmed": True,
        }],
        "parking_access_points": {"PARK": {"point": [12, 20], "source": "approved_parking_target"}},
        "conflict_inventory_complete": True,
        "conflict_zones": [], "protected_zones": [], "pedestrian_reserved_zones": [],
        "fixed_obstacles": [], "reserved_site_regions": [], "setback_zones": [],
        "building_footprints": [],
    }


def _source(access_id="V0", edge="E0", *, ramp=False):
    return {
        "access_id": access_id, "parcel_edge_id": edge,
        "access_edge_reference": edge, "target_level": "PARK",
        "parking_target_reference": "PARK", "status": "feasible",
        "access_elevation": 0.0, "target_elevation": -2.5 if ramp else 0.0,
        "delta_z": -2.5 if ramp else 0.0,
        "absolute_level_difference": 2.5 if ramp else 0.0,
        "required_run": 16.7 if ramp else 0.0,
        "site_fit": True, "access_mode": "vehicle_ramp" if ramp else "direct_at_grade",
        "ramp_geometry_required": ramp, "source": "user_explicit",
        "access_edge_status": "confirmed",
    }


def _contracts(sources=None, width=4.0, system="vehicle_ramp"):
    return (
        {"ramp": {"minimum_width": width, "access_candidates": sources or [_source()]}},
        {"status": "resolved", "selected_system": system},
    )


def _design(site=None, sources=None, width=4.0, system="vehicle_ramp"):
    feasibility, decision = _contracts(sources, width, system)
    return VehicleSiteAccessCandidateGeometryDesignReasonerV1().design(
        site or _site(), feasibility, decision
    )


def test_scenario_a_unique_frontage_reaches_coordinator_selector_and_geometry():
    site = _site()
    design = _design(site)
    assert design["selection_status"] == "candidate_selected_for_coordination"
    candidate = design["selected_candidate"]
    assert candidate["access_point"] == [12.0, 0.0]
    assert candidate["entrance_interval"] == [[10.0, 0.0], [14.0, 0.0]]
    assert len(candidate["driveway_corridor"]) == 4
    pedestrian = {"candidates": [{
        "candidate_id": "P1", "access_edge_reference": "E0",
        "access_segment": [[2, 0], [3, 0]], "access_point": [2.5, 0],
        "approach_line": [[2.5, 0], [2.5, 10]], "candidate_score": 100,
        "geometry_status": "candidate",
    }]}
    coordination = SiteAccessCoordinationReasonerV1().coordinate(
        pedestrian, {"selected_system": "vehicle_ramp", "ramp": {"access_candidates": design["access_candidates"]}},
        {"pedestrian_access_required": True, "vehicle_access_required": True,
         "minimum_clear_separation": 3.0, "protected_zones": [], "parking_circulation_zones": []},
    )
    assert coordination["selection_status"] == "resolved"
    feasibility, decision = _contracts(design["access_candidates"])
    selection = VehicleAccessCandidateSelector().select(
        feasibility, decision, {"site_access_coordination": coordination}
    )
    assert selection["status"] == "resolved"
    geometry_site = dict(site)
    geometry_site["parking_access_points"] = {"PARK": [12, 20]}
    resolved = VehicleAccessGeometryResolverV1().resolve(
        selection, {
            "site_geometry": geometry_site, "vertical_geometry": [],
            "physical_walls": [{"wall_id": "PARK-S", "floor": "PARK",
                                "start": [0, 0], "end": [20, 0],
                                "is_exterior": True, "thickness": 0.30}],
            "project_requirements": {"vehicle_access": {"entrances": [{
                "access_id": "V0", "served_level": "PARK", "clear_width": 4.0,
                "clear_height": 2.4, "opening_role": "parking_vehicle_entrance",
                "source": "legacy_fixture_migration", "evidence_status": "authoritative",
            }]}},
        }, {}
    )
    assert resolved["status"] == "resolved"
    assert resolved["entrance"]["entrance_center"] == [12.0, 0.0]


def test_scenario_b_two_equivalent_frontages_remain_pending_tie():
    site = _site()
    site["parcel_edges"] = [
        {"id": "E0", "access_id": "V0", "start": [0, 0], "end": [20, 0], "confirmed": True},
        {"id": "E2", "access_id": "V2", "start": [20, 30], "end": [0, 30], "confirmed": True},
    ]
    site["parking_access_points"] = {"PARK": {"point": [10, 15], "source": "approved_parking_target"}}
    result = _design(site, [_source("V0", "E0"), _source("V2", "E2")])
    assert result["selection_status"] == "pending_tie"
    assert result["selected_candidate"] is None


def test_scenario_c_building_conflict_rejects_straight_driveway_without_curve():
    site = _site()
    site["building_footprints"] = [[[9, 5], [15, 5], [15, 15], [9, 15]]]
    result = _design(site)
    assert result["access_candidates"][0]["geometry_status"] == "not_feasible"
    assert result["access_candidates"][0]["selection_reason"] == "driveway_corridor_intersects_building"


def test_scenario_d_protected_zone_rejects_corridor_without_alternate_path():
    site = _site()
    site["protected_zones"] = [{"polygon": [[9, 6], [15, 6], [15, 9], [9, 9]]}]
    result = _design(site)
    assert result["access_candidates"][0]["geometry_status"] == "not_feasible"
    assert result["access_candidates"][0]["driveway_centerline"] == [[12.0, 0.0], [12.0, 20.0]]


def test_scenario_e_missing_parking_target_stays_pending():
    site = _site()
    site["parking_access_points"] = {}
    result = _design(site)
    assert result["selection_status"] == "pending"
    assert "authoritative_parking_target" in result["unresolved_evidence"]


def test_scenario_f_missing_width_stays_pending_without_default():
    result = _design(width=None)
    assert result["selection_status"] == "pending"
    assert "vehicle_entrance_clear_width" in result["unresolved_evidence"]


def test_scenario_g_ramp_transition_uses_explicit_dimensions():
    source = _source(ramp=True)
    source.update({"ramp_transition_length": 4.0, "ramp_transition_width": 4.0})
    result = _design(sources=[source])
    candidate = result["selected_candidate"]
    assert candidate["ramp_required"] is True
    assert candidate["ramp_transition_zone"]["length"] == 4.0


def test_scenario_h_incomplete_ramp_transition_stays_pending():
    result = _design(sources=[_source(ramp=True)])
    assert result["selection_status"] == "pending"
    assert "complete_ramp_transition_dimensions" in result["unresolved_evidence"]


def test_scenario_i_direct_at_grade_has_no_ramp_transition():
    result = _design()
    candidate = result["selected_candidate"]
    assert candidate["ramp_required"] is False
    assert candidate["ramp_transition_zone"] is None


def test_scenario_j_coordinator_consumes_all_generated_vehicle_candidates():
    design = _design()
    pedestrian = {"candidates": [{
        "candidate_id": "P1", "access_edge_reference": "E0", "access_segment": [[2, 0], [3, 0]],
        "access_point": [2.5, 0], "approach_line": [[2.5, 0], [2.5, 10]],
        "candidate_score": 10.0, "geometry_status": "candidate",
    }]}
    result = SiteAccessCoordinationReasonerV1().coordinate(
        pedestrian, {"selected_system": "vehicle_ramp", "ramp": {"access_candidates": design["access_candidates"]}},
        {"pedestrian_access_required": True, "vehicle_access_required": True,
         "minimum_clear_separation": 3.0, "protected_zones": [], "parking_circulation_zones": []},
    )
    assert result["selection_status"] == "resolved"
    assert result["selected_pair"]["vehicle_candidate_id"].startswith("VEH-")


def test_scenario_k_architecture_first_projection_bypasses_legacy_sampling():
    site = _site()
    site["parking_access_points"] = {"PARK": {"point": [7, 20], "source": "approved_parking_target"}}
    candidate = _design(site)["selected_candidate"]
    assert candidate["access_point"] == [7.0, 0.0]
    assert candidate["access_point"][0] not in (5.0, 10.0, 15.0)
    assert "parking_target_projection_to_frontage" in candidate["source_evidence"]


def test_absent_conflict_inventory_is_not_treated_as_empty():
    site = _site()
    del site["conflict_inventory_complete"]
    result = _design(site)
    assert result["selection_status"] == "pending"
    assert "complete_conflict_inventory" in result["unresolved_evidence"]
