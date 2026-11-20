import json
from math import pi
from pathlib import Path

import pytest
from shapely.geometry import Polygon, box

from core.architecture.reasoning.far_end_operational_turn_v2 import (
    FarEndOperationalTurnV2, ParkingEntranceClearHeightContractV1,
    ParkingSizeClassContractV1, RampOperationalEndV1, RampWidthTransitionV1)
from core.architecture.reasoning.ramp_centerline_topology_v2 import RampCenterlineTopologyV2
from core.architecture.reasoning.authoritative_ramp_endpoint_binding_contract_v1 import AuthoritativeRampEndpointBindingContractV1
from core.architecture.reasoning.project_level_contract_v1 import ProjectLevelContractV1

ROOT=Path(__file__).resolve().parents[2]


def binding(start=0.0,end=-2.4):
    confirmations=[{"kind":"level_elevation","level":key,"value":value,"unit":"m",
        "authority_class":"PROJECT_REQUIREMENT","provenance":["test_project_requirement"]}
        for key,value in (("ramp_start",start),("ramp_arrival",end))]
    return AuthoritativeRampEndpointBindingContractV1().resolve(
        ProjectLevelContractV1().resolve(confirmations=confirmations))


def test_zero_terminal_leg_facing_wall_fails():
    result=RampOperationalEndV1().resolve([[10,3.5],[10,6.5]],list(box(0,0,10,10).exterior.coords)[:-1],3,-2.4,[1,0],-2.4)
    assert result["geometry_status"]=="not_feasible"
    assert "end_facing_away_from_drivable_space" in result["failure_reasons"]


def test_zero_terminal_leg_with_full_direct_field_interface_can_pass():
    result=RampOperationalEndV1().resolve([[5,1],[5,4]],[(5,0),(10,0),(10,5),(5,5)],3,-2.4,[1,0],-2.4)
    assert result["geometry_status"]=="resolved" and result["interface_length"]==pytest.approx(3)


def test_nonzero_terminal_leg_created_by_earlier_tangent_can_pass_end():
    t=RampCenterlineTopologyV2().construct([1.5,0],[0,1],7,"right",pi/2,5,3.5,2,0,.15,-2.4)
    end=t["end_point"]
    field=[(end[0],end[1]-2.5),(end[0]+5,end[1]-2.5),(end[0]+5,end[1]+2.5),(end[0],end[1]+2.5)]
    assert t["leg_2_length"]==2
    assert RampOperationalEndV1().resolve(t["end_edge"],field,3,-2.4,t["end_heading"],-2.4)["geometry_status"]=="resolved"


def test_small_parking_width_transition_is_continuous():
    t=RampCenterlineTopologyV2().construct([1.5,0],[0,1],7,"right",pi/2,5,3.5,2,0,.15,-2.4)
    c=RampWidthTransitionV1().resolve(t,3,3.5,3)
    assert c["entry_width"]==3 and c["curve_width"]==3.5
    assert c["minimum_actual_clear_width"]==3
    assert c["abrupt_width_discontinuity"] is False
    assert c["widening_transition_length"]==pytest.approx(7)


def test_parking_size_class_is_capacity_driven():
    r=ParkingSizeClassContractV1()
    assert r.resolve(2,3)["parking_size_class"]=="small"
    assert r.resolve(2,4)["parking_size_class"]=="medium"
    assert r.resolve(2,26)["parking_size_class"]=="large"


def test_reduced_entrance_height_requires_both_private_and_separate_pedestrian():
    r=ParkingEntranceClearHeightContractV1()
    assert r.resolve("small",True,True)["required_vehicle_entrance_clear_height"]==1.95
    assert r.resolve("small",True,None)["required_vehicle_entrance_clear_height"]==2.10
    assert r.resolve("small",False,True)["required_vehicle_entrance_clear_height"]==2.10
    assert r.resolve("medium",True,True)["required_vehicle_entrance_clear_height"]==2.10


@pytest.fixture(scope="module")
def real_result():
    source=sorted((ROOT/"exports"/"DEFAULT").glob("parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json"))[-1]
    base=json.loads(source.read_text());base["requirements"]["ramp"]["minimum_inner_turn_radius"]=5.
    result=FarEndOperationalTurnV2().resolve(base["site"]["parcel"],base["site"]["frontage"],
        base["physical_basement_wall"],base["requirements"],{"status":"required","slope":.15,
        "authoritative_ramp_endpoint_binding":binding()})
    return result


def test_real_search_begins_with_fields_and_reports_staged_failure(real_result):
    if real_result["hard_valid_candidates"]:
        assert real_result["first_failure_stage"] is None
    else:
        assert real_result["first_failure_stage"] in {"no_valid_end_interface","R5_curve_outside_envelope","no_complete_vehicle_operation_chain","minimum_independently_usable_stall_count_not_met"}
    assert real_result["parking_size_class_contract"]["parking_size_class"]=="small"
    assert real_result["parking_size_class_contract"]["minimum_entrance_ramp_width"]==3


def test_real_search_never_publishes_physical_ramp(real_result):
    assert real_result["physical_ramp_published"] is False
    assert real_result["human_visual_acceptance"]=="pending"


def test_real_valid_candidates_preserve_operational_end_but_stop_downstream_on_short_edge(real_result):
    valid=[c for c in real_result["candidates"] if c.get("ramp_operational_end_status")=="hard_valid"]
    assert valid
    for c in valid:
        assert c["terminal_leg"]["nonzero"]
        assert c["operational_end"]["geometry_status"]=="resolved"
        assert c["geometry_status"]=="not_feasible"
        assert c["physical_path_length_contract"]["geometry_status"]=="insufficient_physical_edge_run"
        assert c["parking_search_status"]=="not_run_upstream_ramp_invalid"
