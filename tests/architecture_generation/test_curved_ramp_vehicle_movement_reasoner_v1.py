import json
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon

from core.architecture.reasoning.curved_ramp_vehicle_movement_reasoner_v1 import CurvedRampVehicleMovementReasonerV1


ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def curved_result():
    source=sorted((ROOT/"exports"/"DEFAULT").glob("parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json"))[-1]
    base=json.loads(source.read_text(encoding="utf-8"));base["requirements"]["ramp"]["minimum_inner_turn_radius"]=5.0
    request={"contract":"RampTopologyChangeRequestV1","status":"required","slope":.15}
    result=CurvedRampVehicleMovementReasonerV1().resolve(base["site"]["parcel"],base["site"]["frontage"],
        base["physical_basement_wall"],base["requirements"],{"inventory_status":"complete_empty"},request)
    return base,result


def test_search_is_strictly_gated_by_required_topology_request(curved_result):
    base,_=curved_result
    result=CurvedRampVehicleMovementReasonerV1().resolve(base["site"]["parcel"],base["site"]["frontage"],
        base["physical_basement_wall"],base["requirements"],{"inventory_status":"complete_empty"},
        {"contract":"RampTopologyChangeRequestV1","status":"pending","slope":.15})
    assert result["status"]=="not_run" and result["candidates"]==[]


def test_radius_contract_distinguishes_inner_centerline_outer(curved_result):
    _,result=curved_result
    for candidate in (c for c in result["candidates"] if c["topology"]=="perimeter_curved_turn"):
        assert candidate["inner_radius"]>=5.0
        assert candidate["centerline_radius"]==pytest.approx(candidate["inner_radius"]+1.75)
        assert candidate["outer_radius"]==pytest.approx(candidate["inner_radius"]+3.5)


def test_curved_transition_is_real_and_full_width(curved_result):
    _,result=curved_result
    for candidate in result["candidates"]:
        assert Polygon(candidate["transition_polygon"]).area>0
        assert candidate["clear_width"]==pytest.approx(3.5)
        assert len(candidate["inner_arc"])>3 and len(candidate["outer_arc"])>3


def test_arc_length_contributes_to_exact_effective_run(curved_result):
    _,result=curved_result
    for candidate in (c for c in result["candidates"] if c["topology"]=="perimeter_curved_turn"):
        assert candidate["centerline_arc_length"]==pytest.approx(candidate["centerline_radius"]*candidate["turn_angle_radians"])
        assert candidate["leg_1_length"]+candidate["centerline_arc_length"]+candidate["leg_2_length"]==pytest.approx(16.0)
        assert candidate["effective_run"]==pytest.approx(candidate["required_run"])


def test_z_profile_is_continuous_and_descending(curved_result):
    _,result=curved_result
    for candidate in (c for c in result["candidates"] if c["topology"]=="perimeter_curved_turn"):
        z=[point[2] for point in candidate["centerline_3d"]]
        assert z[0]==pytest.approx(0.0) and z[-1]==pytest.approx(-2.4)
        assert all(a>=b for a,b in zip(z,z[1:]))
        assert candidate["z_at_tangent_in"]>candidate["z_at_tangent_out"]


def test_tangent_points_are_bound_to_arc_endpoints(curved_result):
    _,result=curved_result
    for candidate in (c for c in result["candidates"] if c["topology"]=="perimeter_curved_turn"):
        assert candidate["tangent_point_in"]==pytest.approx(candidate["centerline_arc"][0])
        assert candidate["tangent_point_out"]==pytest.approx(candidate["centerline_arc"][-1])


def test_point_contact_or_narrow_interface_never_becomes_hard_valid(curved_result):
    _,result=curved_result
    for candidate in result["candidates"]:
        for trial in candidate["maneuvering_trials"]:
            proof=trial["connection_proof"]
            if proof["minimum_bottleneck_width"]<3.5-1e-7:
                assert proof["geometry_status"]=="not_feasible"


def test_no_invalid_vehicle_movement_is_published(curved_result):
    _,result=curved_result
    for candidate in result["candidates"]:
        movement=candidate.get("vehicle_movement_path")
        if movement and movement["geometry_status"]!="resolved":
            assert candidate["geometry_status"]=="not_feasible"
        if movement:
            assert movement["renderer_authority"]=="production_contract_only"


def test_central_field_evidence_is_preserved_for_ranking(curved_result):
    _,result=curved_result
    for candidate in result["candidates"]:
        assert candidate["central_field_intrusion_area"]>=0
        assert candidate["largest_contiguous_remaining_free_field"]>=0
        assert 0<=candidate["perimeter_adjacency"]<=1+1e-7


def test_no_physical_ramp_or_structure_is_published(curved_result):
    _,result=curved_result
    assert result["physical_ramp_published"] is False
    encoded=json.dumps(result)
    assert '"physical_columns"' not in encoded and '"physical_beams"' not in encoded


def test_generation_is_deterministic(curved_result):
    base,result=curved_result
    again=CurvedRampVehicleMovementReasonerV1().resolve(base["site"]["parcel"],base["site"]["frontage"],
        base["physical_basement_wall"],base["requirements"],{"inventory_status":"complete_empty"},
        {"contract":"RampTopologyChangeRequestV1","status":"required","slope":.15})
    assert [(c["candidate_id"],c["ramp_surface"],c["failure_reasons"]) for c in again["candidates"]]==[
        (c["candidate_id"],c["ramp_surface"],c["failure_reasons"]) for c in result["candidates"]]
