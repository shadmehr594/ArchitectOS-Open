from core.architecture.reasoning.site_access_coordination_reasoner_v1 import (
    SiteAccessCoordinationReasonerV1,
)


def _ped(candidate_id="P1", edge="E0", interval=None, line=None, score=100.0):
    interval = interval or [[4, 0], [5, 0]]
    line = line or [[4.5, 0], [4.5, 10]]
    return {
        "candidate_id": candidate_id,
        "access_edge_reference": edge,
        "access_segment": interval,
        "access_point": line[0],
        "approach_line": line,
        "candidate_score": score,
        "geometry_status": "candidate",
        "evidence_used": ["architecture_first_pedestrian_access_design"],
    }


def _vehicle(candidate_id="V1", edge="E0", interval=None, corridor=None, score=50.0):
    interval = interval or [[10, 0], [14, 0]]
    corridor = corridor or [[12, 0], [12, 20]]
    return {
        "access_id": candidate_id,
        "access_edge_reference": edge,
        "entrance_interval": interval,
        "access_point": [(interval[0][0] + interval[1][0]) / 2, (interval[0][1] + interval[1][1]) / 2],
        "driveway_corridor": corridor,
        "clear_width": 4.0,
        "candidate_score": score,
        "status": "feasible",
    }


def _run(pedestrians, vehicles, **requirements):
    return SiteAccessCoordinationReasonerV1().coordinate(
        {"candidates": pedestrians},
        {"selected_system": "direct_at_grade", "ramp": {"access_candidates": vehicles}},
        {
            "pedestrian_access_required": True,
            "vehicle_access_required": True,
            "minimum_clear_separation": 3.0,
            "protected_zones": [],
            "parking_circulation_zones": [],
            **requirements,
        },
    )


def test_scenario_a_separate_frontage_intervals_resolve_unique_pair():
    result = _run([_ped()], [_vehicle()])
    assert result["selection_status"] == "resolved"
    pair = result["selected_pair"]
    assert pair["overlap_status"] == "clear"
    assert pair["interval_separation"] == 5.0
    assert pair["pedestrian_candidate_id"] == "P1"
    assert pair["vehicle_candidate_id"] == "V1"


def test_scenario_b_overlapping_gates_are_not_feasible():
    result = _run([_ped(interval=[[4, 0], [6, 0]])], [_vehicle(interval=[[5, 0], [9, 0]])])
    assert result["selected_pair"] is None
    assert result["pairs"][0]["coordination_status"] == "not_feasible"
    assert result["pairs"][0]["overlap_status"] == "overlap"


def test_scenario_c_uncontrolled_driveway_crossing_is_rejected():
    pedestrian = _ped(line=[[4.5, 0], [14, 10]])
    vehicle = _vehicle(corridor=[[12, 0], [12, 20]])
    result = _run([pedestrian], [vehicle])
    assert result["selected_pair"] is None
    assert result["pairs"][0]["crossing_status"] == "conflict"
    assert "uncontrolled_pedestrian_vehicle_crossing" in result["pairs"][0]["rejection_reasons"]


def test_scenario_d_equal_pairs_remain_pending_tie():
    pedestrians = [
        _ped("P1", interval=[[1, 0], [2, 0]], line=[[1.5, 0], [1.5, 10]]),
        _ped("P2", interval=[[18, 0], [19, 0]], line=[[18.5, 0], [18.5, 10]]),
    ]
    vehicles = [
        _vehicle("V1", interval=[[7, 0], [11, 0]], corridor=[[9, 0], [9, 20]]),
        _vehicle("V2", interval=[[7, 0], [11, 0]], corridor=[[10, 0], [10, 20]]),
    ]
    result = _run(pedestrians, vehicles)
    assert result["selection_status"] == "pending_tie"
    assert result["selected_pair"] is None


def test_scenario_e_missing_same_frontage_separation_requirement_fails_closed():
    result = _run([_ped()], [_vehicle()], minimum_clear_separation=None)
    assert result["selection_status"] == "coordination_pending"
    assert "minimum_clear_separation_required" in result["unresolved_evidence"]


def test_scenario_f_different_edges_resolve_when_other_evidence_is_clear():
    result = _run([_ped(edge="E0")], [_vehicle(edge="E1")])
    assert result["selection_status"] == "resolved"
    assert result["selected_pair"]["same_edge"] is False
    assert result["selected_pair"]["separation_status"] == "not_applicable"


def test_scenario_g_pedestrian_only_program_does_not_require_vehicle_candidate():
    result = SiteAccessCoordinationReasonerV1().coordinate(
        {"candidates": [_ped()]}, {"ramp": {"access_candidates": []}},
        {"pedestrian_access_required": True, "vehicle_access_required": False},
    )
    assert result["selection_status"] == "pedestrian_only_resolved"
    assert result["selected_pair"]["pedestrian_candidate_id"] == "P1"


def test_scenario_h_explicit_vehicle_only_program_does_not_invent_pedestrian_gate():
    result = SiteAccessCoordinationReasonerV1().coordinate(
        {"candidates": []},
        {"selected_system": "direct_at_grade", "ramp": {"access_candidates": [_vehicle()]}},
        {"pedestrian_access_required": False, "vehicle_access_required": True},
    )
    assert result["selection_status"] == "vehicle_only_resolved"
    assert result["selected_pair"]["pedestrian_candidate_id"] is None


def test_real_orchestrator_gates_both_publications_on_resolved_coordination():
    from core.intelligence.architectural_intelligence_orchestrator import (
        ArchitecturalIntelligenceOrchestrator,
    )

    pedestrian = _ped()
    geometry = {
        "site_geometry": {
            "parcel_boundary": [[0, 0], [20, 0], [20, 30], [0, 30]],
            "parcel_edges": [{
                "id": "E0", "access_id": "V1", "edge_index": 0,
                "start": [0, 0], "end": [20, 0], "confirmed": True,
            }],
            "pedestrian_access_design": {"candidates": [pedestrian]},
            "site_access_coordination_requirements": {
                "minimum_clear_separation": 3.0,
                "protected_zones": [],
                "parking_circulation_zones": [],
            },
            "parking_access_points": {"basement": [12, 20]},
            "parking_access_points_source": "approved_parking_target",
            "conflict_inventory_complete": True,
            "conflict_zones": [],
        },
        "floor_geometry": [{"floor": "F1", "footprint": {"points": [[3, 10], [17, 10], [17, 25], [3, 25]]}}],
        "spaces": [], "openings": [], "vertical_geometry": [],
        "physical_walls": [{
            "wall_id": "B-S", "floor": "basement", "start": [0, 0], "end": [20, 0],
            "is_exterior": True, "thickness": 0.30,
        }],
        "project_requirements": {"vehicle_access": {"entrances": [{
            "access_id": "V1", "served_level": "basement", "clear_width": 3.5,
            "clear_height": 2.4, "opening_role": "basement_vehicle_entrance",
            "source": "legacy_fixture_migration", "evidence_status": "authoritative",
        }]}},
    }
    context = {
        "requirements": ["parking"], "floors": [],
        "site": {"area": 600.0, "bbox": {"width": 20.0, "height": 30.0}},
        "site_constraints": {"access_elevations": [{
            "id": "V1", "parcel_edge_id": "E0", "access_edge_reference": "E0",
            "type": "road", "elevation": -2.5, "vehicle_access": True,
            "source": "user_explicit", "access_edge_status": "confirmed",
            "entrance_interval": [[10, 0], [14, 0]],
            "access_point": [12, 0], "driveway_corridor": [[12, 0], [12, 20]],
            "candidate_score": 50.0,
            "building_entry_allowed": True,
        }]},
        "parking": {"level": "basement", "elevation": -2.5},
        "allowable_vehicle_ramp_slope_percent": 15.0,
        "minimum_vehicle_ramp_width": 3.5,
        "vehicle_turning_radius": 5.5,
        "minimum_pedestrian_vehicle_separation": 3.0,
        "architectural_geometry": geometry,
    }
    result = ArchitecturalIntelligenceOrchestrator().analyze(context)
    assert result["site_access_coordination"]["selection_status"] == "resolved"
    assert result["architectural_geometry"]["site_geometry"]["pedestrian_access"]["access_id"] == "P1"
    assert result["vehicle_access_geometry"]["status"] == "resolved"
    assert result["vehicle_access_geometry"]["entrance"]["entrance_center"] == [12.0, 0.0]
