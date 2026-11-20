from copy import deepcopy

import pytest

from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import (
    BasementRampParkingDesignReasonerV2,
)
from core.site.separation_joint_engine import SeparationJointEngine
from shapely.geometry import Polygon, box


PARCEL = [[9.495348, 22.127313], [0.0, 18.990695], [6.273236, 0.0], [15.768583, 3.136618]]
FRONTAGE = [PARCEL[0], PARCEL[1]]


def inputs():
    engine = SeparationJointEngine()
    wall = {
        "outer_face": engine.resolve_buildable_envelope(PARCEL, {"edge_offsets": [0, .1, .1, .1]})["buildable_boundary"],
        "centerline": engine.resolve_buildable_envelope(PARCEL, {"edge_offsets": [.1, .2, .2, .2]})["buildable_boundary"],
        "inner_face": engine.resolve_buildable_envelope(PARCEL, {"edge_offsets": [.2, .3, .3, .3]})["buildable_boundary"],
    }
    requirements = {
        "levels": {"ground": 0.0, "basement": -2.4},
        "ramp": {"clear_width": 3.5, "maximum_longitudinal_slope": .17,
                 "allowable_slope_candidates": [.15, .16, .17], "required_headroom": 2.2},
        "parking": {"minimum_count": 2, "stall_width": 2.5, "stall_depth": 5.0,
                    "aisle_width": 5.0, "minimum_turning_radius": 5.0,
                    "maneuvering_clear_zone": {"preferred": [5.0, 5.0], "minimum": [4.5, 4.5]}},
        "core": {"stair_clear_width": 1.2, "stair_reserved_zone": [2.4, 4.2],
                 "elevator_shaft_clear": [1.8, 1.8], "enclosure_wall_thickness": .2,
                 "lobby_clear": [1.5, 1.5], "maximum_width": 4.5,
                 "maximum_depth": 5.5, "elevator_required": True},
    }
    return wall, requirements


def test_core_sizing_uses_current_project_evidence_and_preserves_configurations():
    wall, requirements = inputs()
    result = BasementRampParkingDesignReasonerV2().design(
        PARCEL, FRONTAGE, wall, requirements, {"inventory_status": "complete_empty"}
    )
    core = result["core_sizing"]
    assert core["geometry_status"] == "resolved"
    sizes = [(x["minimum_width"], x["minimum_depth"]) for x in core["configurations"]]
    assert sizes[0] == pytest.approx((4.4, 4.2))
    assert sizes[1] == pytest.approx((4.2, 4.4))


def test_real_parcel2_does_not_turn_radius_into_mandatory_circle_and_fails_coordinated_fit():
    wall, requirements = inputs()
    result = BasementRampParkingDesignReasonerV2().design(
        PARCEL, FRONTAGE, wall, requirements, {"inventory_status": "complete_empty"}
    )
    assert result["status"] == "not_feasible"
    assert result["selection_status"] == "unresolved_no_feasible_solution"
    assert result["selected_candidate"] is None
    assert result["automated_geometry_pass"] is False
    assert len(result["candidates"]) >= 24
    assert not [c for c in result["candidates"] if c["geometry_status"] == "candidate"]
    assert result["diagnostic"]["basement_inner_clear_width"] == pytest.approx(9.4)
    assert result["diagnostic"]["mandatory_turning_circle"] is False
    assert result["diagnostic"]["maneuvering_minimum_size"] == [4.5, 4.5]
    assert any(len(c["parking_stalls"]) == 2 for c in result["candidates"])
    assert all(c["ramp_slab_void"] is None for c in result["candidates"])


def test_design_is_deterministic_and_never_promotes_a_rejected_candidate():
    wall, requirements = inputs()
    reasoner = BasementRampParkingDesignReasonerV2()
    first = reasoner.design(PARCEL, FRONTAGE, wall, requirements, {"inventory_status": "complete_empty"})
    second = reasoner.design(deepcopy(PARCEL), deepcopy(FRONTAGE), deepcopy(wall),
                             deepcopy(requirements), {"inventory_status": "complete_empty"})
    assert first == second
    assert first["selected_candidate"] is None
    assert first["human_visual_acceptance"] == "pending"


def test_slope_runs_and_downward_surface_are_evidence_derived():
    wall, requirements = inputs()
    result = BasementRampParkingDesignReasonerV2().design(
        PARCEL, FRONTAGE, wall, requirements, {"inventory_status": "complete_empty"})
    straight = [c["ramp"] for c in result["candidates"] if c["ramp"]["family"] == "straight"]
    runs = {round(r["slope"], 2): r["run"] for r in straight}
    assert runs[.15] == pytest.approx(16.0)
    assert runs[.16] == pytest.approx(15.0)
    assert runs[.17] == pytest.approx(2.4/.17)
    for ramp in straight:
        assert ramp["start_elevation"] == 0.0
        assert ramp["end_elevation"] == -2.4
        zs = [vertex[2] for vertex in ramp["surface_3d"]["vertices"]]
        assert max(zs) == 0.0 and min(zs) == -2.4


def test_l_family_is_downstream_only_and_turn_contract_is_explicitly_usable():
    wall, requirements = inputs()
    result = BasementRampParkingDesignReasonerV2().design(
        PARCEL, FRONTAGE, wall, requirements, {"inventory_status": "complete_empty"})
    l_ramps = [c for c in result["candidates"] if c["ramp"]["family"] == "l_shaped"]
    assert not l_ramps  # all straight slopes found connectedbots? 
    resolver=BasementRampParkingDesignReasonerV2()
    candidate={"family":"l_shaped","width":3.5,"run":16.0,"leg1":10.0,
        "local_polygon":box(0,0,8,12),"transition_polygon":box(0,8.25,5,11.75),
        "incoming_direction_local":[0,1],"outgoing_direction_local":[1,0],
        "transition_center_path_local":[[1.75,8.25],[1.75,9.125],[2.625,10],[3.5,10]]}
    turn=resolver._turn_geometry(candidate,box(-1,-1,20,20),0.0,-2.4)
    assert turn["geometry_status"]=="resolved"
    assert turn["turn_validation_level"]=="topology_clearance"
    assert turn["minimum_usable_width"]>=3.5
    assert turn["transition_entry_elevation"]>turn["transition_exit_elevation"]


def test_maneuvering_search_allows_lateral_placement_and_aisle_overlap():
    wall, requirements = inputs()
    result = BasementRampParkingDesignReasonerV2().design(
        PARCEL, FRONTAGE, wall, requirements, {"inventory_status": "complete_empty"})
    searched = [c for c in result["candidates"]
                if c["maneuvering_clear_zone_contract"]["placement_role"] != "old_serial_diagnostic"]
    assert searched
    assert all(c["maneuvering_clear_zone_contract"]["aisle_overlap"] for c in searched)
    assert any(c["maneuvering_envelope"] != c["old_invalid_serial_maneuvering_polygon"] for c in searched)
    assert any(c["ramp"]["slope"] == .15 and len(c["parking_stalls"]) == 2 for c in searched)
    assert any(c["ramp"]["slope"] == .17 and len(c["parking_stalls"]) == 2 for c in searched)


def test_preview_projection_consumes_contract_vertices_without_reconstructing_z():
    from tools.generate_parcel2_basement_v2_design import project_ramp_surface_from_contract
    wall, requirements = inputs()
    result = BasementRampParkingDesignReasonerV2().design(
        PARCEL, FRONTAGE, wall, requirements, {"inventory_status": "complete_empty"})
    ramp = next(c["ramp"] for c in result["candidates"] if c["ramp"]["family"] == "straight")
    preview = project_ramp_surface_from_contract(ramp)
    assert preview["vertices_3d"] is ramp["surface_3d"]["vertices"]
    assert preview["faces"] is ramp["surface_3d"]["faces"]
    start_z = [v[2] for v in preview["vertices_3d"] if v[2] == 0.0]
    end_z = [v[2] for v in preview["vertices_3d"] if v[2] == -2.4]
    assert start_z == [0.0, 0.0]
    assert end_z == [-2.4, -2.4]
    assert sum(start_z)/2 > sum(end_z)/2
    semantic = ramp["semantic_edges"]
    assert semantic["status"] == "resolved"
    assert semantic["start_z"] == 0.0
    assert semantic["end_z"] == -2.4
    assert semantic["descent_direction"] == "road_to_basement"


def test_parking_and_future_structure_contracts_preserve_architectural_boundaries():
    wall, requirements = inputs()
    result = BasementRampParkingDesignReasonerV2().design(
        PARCEL, FRONTAGE, wall, requirements, {"inventory_status": "complete_empty"})
    candidate = next(c for c in result["candidates"] if len(c["parking_stalls"]) == 2)
    parking = candidate["parking_architectural_intelligence"]
    assert parking["maneuvering_aisle_shared"] is True
    assert parking["valid_stall_count"] == 2
    assert parking["wall_side_clearance_policy"]["one_constrained_side_width"] == 2.75
    reservation = candidate["structural_compatibility_reservation"]
    assert reservation["contract"] == "StructuralCompatibilityReservationV1"
    assert reservation["physical_columns"] == []
    assert reservation["physical_beams"] == []
    assert candidate["pedestrian_connection"] is None
    assert "pedestrian_protected_route_not_yet_resolved" in candidate["rejection_reasons"]


def test_l_ramp_central_field_intrusion_is_measured_and_penalized():
    resolver=BasementRampParkingDesignReasonerV2()
    perimeter={"perimeter_adjacency_ratio":.8,"central_field_intrusion_area":2,
        "remaining_contiguous_vehicle_field":90,"dead_strip_area":0}
    central={"perimeter_adjacency_ratio":.2,"central_field_intrusion_area":12,
        "remaining_contiguous_vehicle_field":60,"dead_strip_area":4}
    assert resolver._parking_rank(perimeter)>resolver._parking_rank(central)


def test_incomplete_obstacle_inventory_blocks_candidate_generation():
    wall, requirements = inputs()
    result = BasementRampParkingDesignReasonerV2().design(
        PARCEL, FRONTAGE, wall, requirements, {"inventory_status": "unresolved"}
    )
    assert result["status"] == "pending_requirement"
    assert result["candidates"] == []
    assert "complete_fixed_obstacle_inventory" in result["unresolved_evidence"]


def test_ramp_end_escape_is_a_real_connected_contract_not_a_remote_square():
    wall, requirements = inputs()
    result = BasementRampParkingDesignReasonerV2().design(
        PARCEL, FRONTAGE, wall, requirements, {"inventory_status": "complete_empty"})
    resolved = [c for c in result["candidates"] if c["ramp_end_escape"]["geometry_status"] == "resolved"]
    assert resolved
    assert all(c["ramp_end_escape"]["minimum_connection_width"] >= 3.5 for c in resolved)
    assert all(c["ramp_end_escape"]["connected_maneuvering_polygon"] for c in resolved)
    assert any(c["ramp_end_escape"]["right_escape_width"] > 5.0 for c in resolved)


def test_disconnected_maneuvering_field_and_end_facing_wall_fail_closed():
    reasoner = BasementRampParkingDesignReasonerV2()
    inner = box(0, 0, 10, 20)
    ramp = box(3, 0, 6.5, 16)
    disconnected = box(0, 0, 5, 5)
    escape = reasoner._ramp_end_escape(inner, ramp, [[3, 16], [6.5, 16]], [0, 1], disconnected, 3.5)
    assert escape["geometry_status"] == "not_feasible"
    assert "ramp_end_escape_width_insufficient" in escape["failure_reasons"]
    wall_end = reasoner._ramp_end_escape(box(0, 0, 10, 16), ramp, [[3, 16], [6.5, 16]], [0, 1], box(3, 11, 8, 16), 3.5)
    assert "ramp_end_faces_wall" in wall_end["failure_reasons"]


def test_lateral_end_escape_can_pass_without_serial_five_meter_depth():
    reasoner = BasementRampParkingDesignReasonerV2()
    inner = box(0, 0, 10, 20)
    ramp = box(3, 0, 6.5, 16)
    lateral = box(1.5, 16, 6.5, 20)
    escape = reasoner._ramp_end_escape(inner, ramp, [[3, 16], [6.5, 16]], [0, 1], lateral, 3.5)
    assert escape["geometry_status"] == "resolved"
    assert escape["first_obstacle_distance"] == pytest.approx(4.0)


def test_parking_topology_search_is_not_capped_at_two_and_requires_aisle_access():
    reasoner = BasementRampParkingDesignReasonerV2()
    parking = {"stall_width": 2.5, "stall_depth": 5.0}
    options = reasoner._stall_topologies(box(0, 0, 20, 20), box(5, 5, 15, 10),
                                         Polygon(), Polygon(), parking)
    assert max(len(option["stalls"]) for option in options) >= 4
    remote = reasoner._stall_topologies(box(0, 0, 20, 20), box(30, 30, 40, 35),
                                        Polygon(), Polygon(), parking)
    assert remote == []


def test_project_wall_side_policy_changes_required_stall_width():
    resolver = BasementRampParkingDesignReasonerV2()
    assert resolver._required_stall_width(2.5, False, False) == 2.5
    assert resolver._required_stall_width(2.5, True, False) == 2.75
    assert resolver._required_stall_width(2.5, True, True) == 3.0


def test_no_structure_bim_or_ifc_is_published_by_basement_v2():
    wall, requirements = inputs()
    result = BasementRampParkingDesignReasonerV2().design(
        PARCEL, FRONTAGE, wall, requirements, {"inventory_status": "complete_empty"})
    for candidate in result["candidates"]:
        reservation = candidate["structural_compatibility_reservation"]
        assert reservation["physical_columns"] == []
        assert reservation["physical_beams"] == []
        assert "ifc" not in candidate and "bim" not in candidate


def test_shared_arrival_exit_field_supports_each_stall_with_other_occupied():
    reasoner = BasementRampParkingDesignReasonerV2()
    inner=box(0,0,20,20); field=box(2,5,12,10)
    stalls=[box(2,10,4.5,15),box(4.5,10,7,15)]
    escape={"departure_apron_polygon":[[2,5],[5.5,5],[5.5,10],[2,10]],
            "minimum_connection_width":3.5}
    spine=reasoner._vehicle_circulation_spine(inner,[[2,5],[5.5,5]],escape,field,field,stalls)
    assert spine["geometry_status"] == "resolved"
    assert spine["connects_all_stalls"] and spine["supports_return_to_ramp"]
    assert all(item["other_stalls_treated_as_occupied"] for item in spine["stall_results"])
    assert all(item["incoming_path_exists"] and item["outgoing_path_exists"] for item in spine["stall_results"])


def test_five_meter_field_disconnected_by_parking_row_fails_vehicle_spine():
    reasoner=BasementRampParkingDesignReasonerV2();inner=box(0,0,12,20)
    arrival=box(2,5,7,10); aisle=arrival
    # The second occupied rectangle cuts the only topology-clearance route.
    stalls=[box(2,10,4.5,15),box(2,6.5,7,8.5)]
    escape={"departure_apron_polygon":[[2,5],[5.5,5],[5.5,10],[2,10]],"minimum_connection_width":3.5}
    spine=reasoner._vehicle_circulation_spine(inner,[[2,5],[5.5,5]],escape,arrival,aisle,stalls)
    assert spine["geometry_status"] == "not_feasible"
    assert "no_independent_exit_path" in spine["failure_reasons"]


def test_perimeter_packed_equal_capacity_ranks_over_central_intrusion():
    reasoner=BasementRampParkingDesignReasonerV2()
    perimeter={"perimeter_adjacency_ratio":.5,"central_field_intrusion_area":0.0,
               "remaining_contiguous_vehicle_field":80.0,"dead_strip_area":0.0}
    central={"perimeter_adjacency_ratio":0.0,"central_field_intrusion_area":8.0,
             "remaining_contiguous_vehicle_field":70.0,"dead_strip_area":4.0}
    assert reasoner._parking_rank(perimeter)>reasoner._parking_rank(central)


def test_real_candidates_require_connected_spine_and_do_not_count_rectangle_only():
    wall, requirements=inputs()
    result=BasementRampParkingDesignReasonerV2().design(
        PARCEL,FRONTAGE,wall,requirements,{"inventory_status":"complete_empty"})
    with_stalls=[c for c in result["candidates"] if c["parking_stalls"]]
    assert with_stalls
    assert all(c["vehicle_circulation_spine"]["connects_all_stalls"]
               for c in with_stalls if c["vehicle_circulation_spine"]["geometry_status"]=="resolved")
    assert any(c["vehicle_circulation_spine"]["geometry_status"]=="resolved" for c in with_stalls)


def test_parcel2_topology_decisions_distinguish_actual_remaining_depth_and_search_lateral_first():
    wall,requirements=inputs();result=BasementRampParkingDesignReasonerV2().design(
        PARCEL,FRONTAGE,wall,requirements,{"inventory_status":"complete_empty"})
    decisions={round(d["slope"],2):d for d in result["ramp_topology_decisions"]}
    assert decisions[.15]["straight_run"]==pytest.approx(16.0)
    assert decisions[.16]["straight_run"]==pytest.approx(15.0)
    assert decisions[.17]["straight_run"]==pytest.approx(2.4/.17)
    assert decisions[.15]["direct_remaining_depth"]==pytest.approx(3.7,abs=1e-5)
    assert decisions[.16]["direct_remaining_depth"]==pytest.approx(4.7,abs=1e-5)
    assert decisions[.17]["direct_remaining_depth"]==pytest.approx(5.582352,abs=1e-5)
    assert all(d["lateral_connected_maneuvering_searched"] for d in decisions.values())
    assert decisions[.15]["maneuvering_status"]=="preferred_maneuvering_resolved"
    assert decisions[.15]["topology_change_request"] is None


def test_topology_change_request_is_emitted_only_after_connected_search_exhaustion():
    resolver=BasementRampParkingDesignReasonerV2()
    fake={"ramp":{"slope":.15,"family":"straight","run":16.0,"remaining_longitudinal_depth":3.7},
          "ramp_end_escape":{"geometry_status":"not_feasible"},
          "maneuvering_clear_zone_contract":{"selected_size":[4.5,4.5]},"ramp_id":"S"}
    l={"ramp":{"slope":.15,"family":"l_shaped"},"ramp_id":"L-PERIMETER"}
    decision=resolver._topology_decisions([fake,l],[5.0,5.0],[4.5,4.5])[0]
    assert decision["maneuvering_status"]=="maneuvering_requires_topology_change"
    assert decision["topology_change_request"]["contract"]=="RampTopologyChangeRequestV1"
    assert "L-PERIMETER" in decision["turned_alternatives"]


def test_no_slope_is_selected_merely_because_it_is_steepest():
    wall,requirements=inputs();result=BasementRampParkingDesignReasonerV2().design(
        PARCEL,FRONTAGE,wall,requirements,{"inventory_status":"complete_empty"})
    assert result["selected_candidate"] is None
    assert {round(d["slope"],2) for d in result["ramp_topology_decisions"]}=={.15,.16,.17}


def test_piecewise_total_run_is_partitioned_across_legs_and_transition():
    resolver=BasementRampParkingDesignReasonerV2();inner=box(0,0,20,30)
    candidates=resolver._piecewise_ramp_candidates(inner,inner,.15,16.0,3.5,[4.5,4.5])
    assert candidates
    assert {c["piecewise_topology"] for c in candidates}=={"perimeter_turn","dog_leg"}
    for candidate in candidates:
        assert candidate["required_total_run"]==pytest.approx(16.0)
        assert candidate["leg1"]+candidate["transition_effective_run"]+candidate["leg2"]==pytest.approx(16.0)
        assert candidate["total_effective_run"]==pytest.approx(16.0)
        turn=resolver._turn_geometry(candidate,inner,0.0,-2.4)
        assert turn["turn_validation_level"]=="topology_clearance"
        assert turn["transition_entry_elevation"]>turn["transition_exit_elevation"]


def test_optional_entrance_transition_remains_pending_without_length_and_does_not_block():
    wall,requirements=inputs();result=BasementRampParkingDesignReasonerV2().design(
        PARCEL,FRONTAGE,wall,requirements,{"inventory_status":"complete_empty"})
    transition=result["optional_entrance_transition"]
    assert transition["allowable_slope_range"]==[.005,.01]
    assert transition["entrance_transition_length"] is None
    assert transition["geometry_status"]=="pending_requirement"
    assert transition["blocks_continuous_ramp_evaluation"] is False


def test_point_contact_is_not_a_vehicle_width_maneuvering_connection():
    resolver=BasementRampParkingDesignReasonerV2()
    apron=box(0,0,3.5,3.7); maneuver=box(3.5,3.7,8.5,8.7)
    proof=resolver._maneuvering_connection_proof(apron,maneuver,3.5)
    assert proof["geometry_status"]=="not_feasible"
    assert proof["contact_interface_length"]==pytest.approx(0.0)
    assert proof["minimum_bottleneck_width"]==pytest.approx(0.0)
    assert proof["connected_component_count"]==2
    assert "maneuvering_field_disconnected_from_ramp_end" in proof["failure_reasons"]
    assert "ramp_end_escape_width_insufficient" in proof["failure_reasons"]
    assert proof["corridor_polygon"]==[]


def test_real_width_overlap_can_prove_maneuvering_connection():
    resolver=BasementRampParkingDesignReasonerV2()
    apron=box(0,0,3.5,5.0); maneuver=box(0,1.5,5.0,6.5)
    proof=resolver._maneuvering_connection_proof(apron,maneuver,3.5)
    assert proof["geometry_status"]=="resolved"
    assert proof["overlap_area"]==pytest.approx(12.25)
    assert proof["minimum_bottleneck_width"]==pytest.approx(3.5)
    assert proof["connected_component_count"]==1
    assert proof["corridor_polygon"]


def test_piecewise_search_runs_only_for_required_topology_change_contract():
    wall,requirements=inputs();resolver=BasementRampParkingDesignReasonerV2()
    blocked=resolver.resolve_topology_change_request(PARCEL,FRONTAGE,wall,requirements,
        {"inventory_status":"complete_empty"},{"contract":"RampTopologyChangeRequestV1","status":"pending","slope":.15})
    assert blocked["status"]=="not_run"
    assert blocked["candidates"]==[]
    result=resolver.resolve_topology_change_request(PARCEL,FRONTAGE,wall,requirements,
        {"inventory_status":"complete_empty"},{"contract":"RampTopologyChangeRequestV1","status":"required","slope":.15})
    assert result["candidates"]
    assert {c["topology"] for c in result["candidates"]}=={"perimeter_turn","dog_leg"}
    assert all(c["total_effective_run"]==pytest.approx(16.0) for c in result["candidates"])


def test_piecewise_candidates_fail_closed_when_end_contact_has_no_vehicle_width():
    wall,requirements=inputs();result=BasementRampParkingDesignReasonerV2().resolve_topology_change_request(
        PARCEL,FRONTAGE,wall,requirements,{"inventory_status":"complete_empty"},
        {"contract":"RampTopologyChangeRequestV1","status":"required","slope":.15})
    assert result["status"]=="unresolved_no_feasible_piecewise_topology"
    assert result["hard_valid_candidates"]==[]
    assert all(c["geometry_status"]=="not_feasible" for c in result["candidates"])
    assert any("maneuvering_field_disconnected_from_ramp_end" in c["failure_reasons"] for c in result["candidates"])
