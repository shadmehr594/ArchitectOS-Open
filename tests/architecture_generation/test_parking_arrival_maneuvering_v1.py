from core.architecture.geometry.parking_arrival_maneuvering_resolver_v1 import (
    ParkingArrivalManeuveringResolverV1,
)
from tests.architecture_generation.test_complete_architecture_vehicle_access_acceptance import (
    _generate_and_export,
)


def _resolve(requirement=None, target=(10, 10), protected=None, walls=None):
    driveway={"served_level":"basement","centerline":[[10,0],list(target)],"width":3.5}
    opening={"opening_id":"VO","opening_center":[10,0],"geometry_status":"resolved"}
    floors=[{"floor":"basement","footprint":{"points":[[0,0],[20,0],[20,20],[0,20]]}}]
    return ParkingArrivalManeuveringResolverV1().resolve(
        driveway,opening,floors,walls or [],protected or [],requirement or {})


def _requirement(radius=2.0):
    return {"served_level":"basement","minimum_turning_radius":radius,
            "required_clear_width":3.5,"source":"project","evidence_status":"authoritative"}


def test_arrival_zone_is_inside_usable_basement_and_connected_through_opening():
    result=_resolve(_requirement())
    assert result["geometry_status"]=="resolved"
    assert result["entry_interface"]=="VO"
    assert result["arrival_point"]==[10.0,10.0]
    assert result["maneuvering_envelope"]


def test_missing_turning_radius_fails_closed_without_fake_maneuver_geometry():
    req=_requirement(); req.pop("minimum_turning_radius")
    result=_resolve(req)
    assert result["geometry_status"]=="pending"
    assert result["maneuvering_envelope"] is None


def test_insufficient_boundary_or_wall_clearance_is_not_feasible():
    assert _resolve(_requirement(3),target=(1,1))["geometry_status"]=="not_feasible"
    walls=[{"floor":"basement","start":[0,9],"end":[20,9]}]
    assert _resolve(_requirement(2),walls=walls)["geometry_status"]=="not_feasible"


def test_stair_or_protected_zone_collision_is_not_feasible():
    zone={"type":"stair_core","polygon":[[8,8],[12,8],[12,12],[8,12]]}
    assert _resolve(_requirement(),protected=[zone])["geometry_status"]=="not_feasible"


def test_real_south_and_north_both_resolve_parking_arrival():
    _,south,_=_generate_and_export("south_road","south","vehicle_ramp",0.0,16.0,"parking_arrival_south")
    _,north,_=_generate_and_export("north_road","north","direct_at_grade",-2.4,0.0,"parking_arrival_north")
    assert south["parking_arrival"]["geometry_status"]=="resolved"
    assert north["parking_arrival"]["geometry_status"]=="resolved"
