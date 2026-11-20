import pytest

from core.architecture.reasoning.vehicle_access_edge_selection_reasoner_v1 import (
    VehicleAccessEdgeSelectionReasonerV1,
)


def edge(edge_id,z,**extra):
    value={"access_edge_id":edge_id,"geometry":[[0,0],[10,0]],"road_width":10.0,
           "road_elevation":z,"source":"synthetic_authoritative_test_edge",
           "evidence_status":"authoritative_for_current_test","available_geometric_run":20.0,
           "parking_capacity":2,"central_field_fragmentation":0.0}
    value.update(extra);return value


def test_same_level_authoritative_road_selects_direct_at_grade_without_ramp_geometry():
    result=VehicleAccessEdgeSelectionReasonerV1().resolve(
        [edge("ROAD-A",0.0),edge("ROAD-B",-2.4)],-2.4,[.15,.16,.17])
    assert len(result["evaluated_edges"])==2
    assert result["selected_edge"]["access_edge_id"]=="ROAD-B"
    assert result["selected_edge"]["vehicle_access_type"]=="direct_at_grade"
    assert result["selected_edge"]["ramp_required"] is False
    assert result["selected_edge"]["ramp_geometry"] is None
    road_a=next(x for x in result["evaluated_edges"] if x["access_edge_id"]=="ROAD-A")
    assert road_a["hard_valid"] and road_a["required_ramp_runs"]["0.150000"]==pytest.approx(16.0)


def test_smaller_nonzero_delta_derives_shorter_run_when_other_evidence_equal():
    result=VehicleAccessEdgeSelectionReasonerV1().resolve(
        [edge("ROAD-A",0.0),edge("ROAD-B",-1.2)],-2.4,[.15])
    assert result["selected_edge"]["access_edge_id"]=="ROAD-B"
    assert result["selected_edge"]["required_ramp_runs"]["0.150000"]==pytest.approx(8.0)


def test_lowest_elevation_does_not_override_hard_architectural_failure():
    result=VehicleAccessEdgeSelectionReasonerV1().resolve(
        [edge("ROAD-A",0.0),edge("ROAD-B",-2.4,hard_failure_reasons=["vehicle_opening_not_feasible"])],
        -2.4,[.15])
    assert result["selected_edge"]["access_edge_id"]=="ROAD-A"
    rejected=next(x for x in result["evaluated_edges"] if x["access_edge_id"]=="ROAD-B")
    assert not rejected["hard_valid"]


def test_edge_ranking_re_evaluates_parking_capacity_and_is_deterministic():
    reasoner=VehicleAccessEdgeSelectionReasonerV1();edges=[edge("A",0,parking_capacity=2),edge("B",0,parking_capacity=3)]
    first=reasoner.resolve(edges,-2.4,[.15]);second=reasoner.resolve(edges,-2.4,[.15])
    assert first==second
    assert first["selected_edge"]["access_edge_id"]=="B"

