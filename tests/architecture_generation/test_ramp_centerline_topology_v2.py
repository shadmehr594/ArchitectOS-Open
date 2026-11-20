import json
from math import pi
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon, box

from core.architecture.reasoning.ramp_centerline_topology_v2 import (
    Parcel2RampCenterlineSearchV2, PiecewiseRampVerticalProfileV2,
    RampCenterlineTopologyV2, VehicleMovementPathV2)


ROOT=Path(__file__).resolve().parents[2]


def topology():
    # A large synthetic envelope deliberately isolates constructor math.
    return RampCenterlineTopologyV2().construct([10,0],[0,1],3,"left",pi/2,5,3.5,
        16-3-6.75*pi/2,0,.15)


def test_centerline_is_authoritative_and_tangent():
    t=topology()
    assert t["leg_1_end"]==pytest.approx(t["tangent_in"])
    assert t["leg_2_start"]==pytest.approx(t["tangent_out"])
    assert t["leg_1_heading"]==pytest.approx([0,1])
    assert t["leg_2_heading"]==pytest.approx([-1,0])
    assert t["R_inner"]==5 and t["R_centerline"]==6.75 and t["R_outer"]==8.5


def test_surface_is_continuous_constant_width_offset_product():
    t=topology();s=RampCenterlineTopologyV2().surface(t)
    assert s["geometry_status"]=="resolved"
    assert s["clear_width"]==pytest.approx(3.5)
    assert Polygon(s["complete_union_surface"]).is_valid
    assert Polygon(s["curved_annular_surface"]).area>0


def test_stationing_and_z_are_derived_from_total_run():
    t=topology()
    assert t["effective_total_run"]==pytest.approx(16)
    assert t["stationing"]["S3"]== RadiusApprox(16)
    assert t["z_profile"]["vertices"][0][3]==pytest.approx(0)
    assert t["z_profile"]["vertices"][-1][3]==pytest.approx(-2.4)
    assert all(a[3]>=b[3] for a,b in zip(t["z_profile"]["vertices"],t["z_profile"]["vertices"][1:]))


def RadiusApprox(value):
    return pytest.approx(value)


def test_synthetic_end_interface_opens_into_five_by_five_field():
    t=RampCenterlineTopologyV2().construct([10,0],[0,1],5,"left",pi/2,5,3.5,1,0,.15)
    end=t["end_point"];h=t["end_heading"];lat=[-h[1],h[0]]
    p=Polygon([[end[0]-lat[0]*2.5,end[1]-lat[1]*2.5],
               [end[0]+lat[0]*2.5,end[1]+lat[1]*2.5],
               [end[0]+lat[0]*2.5+h[0]*5,end[1]+lat[1]*2.5+h[1]*5],
               [end[0]-lat[0]*2.5+h[0]*5,end[1]-lat[1]*2.5+h[1]*5]])
    assert LineString(t["end_edge"]).intersection(p.boundary).length==pytest.approx(3.5)


def test_vehicle_path_with_two_stalls_and_other_occupied():
    field=box(0,0,20,10);end_edge=[[0,3.25],[0,6.75]];aisle=[[0,5],[15,5]]
    stalls=[[[7.5,5],[10,5],[10,10],[7.5,10]],[[11,5],[13.5,5],[13.5,10],[11,10]]]
    v=VehicleMovementPathV2().resolve(end_edge,[1,0],list(field.exterior.coords)[:-1],aisle,stalls,2.0)
    assert v["geometry_status"]=="resolved"
    assert all(x["other_stalls_treated_as_occupied"] and x["independent_entry"] and x["independent_exit"] for x in v["stall_paths"])
    assert v["renderer_authority"]=="production_contract_only"


def test_long_variable_profile_route_is_not_rejected_for_exceeding_sixteen_metres():
    ctor=RampCenterlineTopologyV2()
    t=ctor.construct([5,0],[0,1],11,"right",pi/2,5,3.5,1,0,.15,-2.4)
    s=ctor.surface(t);profile=t["z_profile"]
    assert t["effective_total_run"]>16
    assert profile["minimum_run_at_maximum_slope"]==pytest.approx(16)
    assert profile["geometry_status"]=="resolved"
    assert max(profile["segment_slopes"].values())<=.15
    assert profile["segment_slopes"]["leg_1"]==pytest.approx(.15)
    assert profile["z_at_tangent_in"]==pytest.approx(-1.65)
    assert profile["end_z"]==pytest.approx(-2.4)
    assert profile["continuous"] and profile["monotonic_descent"]
    assert Polygon(s["complete_union_surface"]).is_valid


def test_long_synthetic_route_has_full_end_interface_to_connected_field():
    t=RampCenterlineTopologyV2().construct([5,0],[0,1],11,"right",pi/2,5,3.5,1,0,.15,-2.4)
    end=t["end_point"];h=t["end_heading"];lat=[-h[1],h[0]]
    field=Polygon([[end[0]-lat[0]*2.5,end[1]-lat[1]*2.5],
        [end[0]+lat[0]*2.5,end[1]+lat[1]*2.5],
        [end[0]+lat[0]*2.5+h[0]*5,end[1]+lat[1]*2.5+h[1]*5],
        [end[0]-lat[0]*2.5+h[0]*5,end[1]-lat[1]*2.5+h[1]*5]])
    interface=LineString(t["end_edge"]).intersection(field.boundary)
    assert interface.length==pytest.approx(3.5)
    assert box(-20,-1,20,30).covers(field)


@pytest.fixture(scope="module")
def real_result():
    source=sorted((ROOT/"exports"/"DEFAULT").glob("parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json"))[-1]
    base=json.loads(source.read_text(encoding="utf-8"));base["requirements"]["ramp"]["minimum_inner_turn_radius"]=5.0
    result=Parcel2RampCenterlineSearchV2().resolve(base["site"]["parcel"],base["site"]["frontage"],
        base["physical_basement_wall"],base["requirements"],
        {"contract":"RampTopologyChangeRequestV1","status":"required","slope":.15})
    return base,result


def test_real_search_does_not_call_or_relabel_v1_gentle_deflections(real_result):
    _,r=real_result
    assert r["supersedes_v1_only_as_search_method"] is True
    assert all(c["topology"]["turn_angle_degrees"]>=45 for c in r["candidates"])
    assert all(c["classification"]!="gentle_deflection" for c in r["candidates"])
    assert r["obsolete_constant_slope_contradiction"]["status"]=="obsolete_constant_slope_contradiction"


def test_real_search_compares_early_midfield_and_far_end_events(real_result):
    _,r=real_result
    kinds={c["classification"] for c in r["candidates"]}
    assert {"early_turn","midfield_turn","far_end_perimeter_turn"}<=kinds
    assert any(c["topology"]["effective_total_run"]>20 and c["topology"]["z_profile"]["geometry_status"]=="resolved" for c in r["candidates"])
    assert all(c["topology"]["z_profile"]["maximum_local_slope"]==pytest.approx(.15) for c in r["candidates"])


def test_real_long_legs_remain_perimeter_aligned_not_rotated(real_result):
    _,r=real_result
    assert all(c["topology"]["leg_1_heading"]==pytest.approx([0,1]) for c in r["candidates"])
    assert all(c["long_leg_perimeter_alignment"]>=.75 for c in r["candidates"])


def test_real_search_is_deterministic_and_does_not_publish(real_result):
    base,r=real_result
    again=Parcel2RampCenterlineSearchV2().resolve(base["site"]["parcel"],base["site"]["frontage"],
        base["physical_basement_wall"],base["requirements"],
        {"contract":"RampTopologyChangeRequestV1","status":"required","slope":.15})
    assert [(c["candidate_id"],c["failure_reasons"]) for c in r["candidates"]]==[(c["candidate_id"],c["failure_reasons"]) for c in again["candidates"]]
    assert r["physical_ramp_published"] is False and r["human_visual_acceptance"]=="pending"
