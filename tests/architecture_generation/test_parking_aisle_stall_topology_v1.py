from core.architecture.geometry.parking_aisle_stall_topology_resolver_v1 import (
    ParkingAisleStallTopologyResolverV1,
)
from tests.architecture_generation.test_complete_architecture_vehicle_access_acceptance import _generate_and_export


ARRIVAL={"served_level":"basement","arrival_point":[5,5],"minimum_turning_radius":1.0,
         "arrival_zone":{"type":"parking_arrival_zone","polygon":[[4,4],[6,4],[6,6],[4,6]]},
         "geometry_status":"resolved"}


def _req(count=2):
    return {"required_parking_count":count,"stall_width":2.5,"stall_depth":3.0,
            "aisle_width":3.0,"aisle_centerline":[[5,5],[15,5]],"stall_sides":["left"],
            "evidence_status":"authoritative"}


def test_basic_parking_layout_has_connected_accessible_stalls():
    result=ParkingAisleStallTopologyResolverV1().resolve(ARRIVAL,_req(),[])
    assert result["geometry_status"]=="resolved"
    assert len(result["parking_stalls"])==2
    assert all(stall["aisle_access"] for stall in result["parking_stalls"])
    assert result["ingress_egress_connectivity"]=="resolved"


def test_missing_dimensions_or_impossible_capacity_fails_closed():
    incomplete=_req();incomplete.pop("stall_width")
    assert ParkingAisleStallTopologyResolverV1().resolve(ARRIVAL,incomplete,[])["geometry_status"]=="pending"
    impossible=_req(10)
    result=ParkingAisleStallTopologyResolverV1().resolve(ARRIVAL,impossible,[])
    assert result["geometry_status"]=="not_feasible"
    assert result["capacity_status"]=="insufficient_capacity"


def test_stall_blocked_by_core_is_rejected():
    zone={"type":"stair_core","polygon":[[6,6],[10,6],[10,10],[6,10]]}
    result=ParkingAisleStallTopologyResolverV1().resolve(ARRIVAL,_req(),[zone])
    assert result["geometry_status"]=="not_feasible"
    assert result["blocked_stalls"]


def test_south_and_north_access_connect_to_real_parking_system():
    _,south,_=_generate_and_export("south_road","south","vehicle_ramp",0.0,16.0,"parking_topology_south")
    _,north,_=_generate_and_export("north_road","north","direct_at_grade",-2.4,0.0,"parking_topology_north")
    for result in (south,north):
        assert result["parking_layout"]["geometry_status"]=="resolved"
        assert len(result["parking_layout"]["parking_stalls"])==2
