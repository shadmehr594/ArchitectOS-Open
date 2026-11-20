from core.architecture.reasoning.spatial_reservation_exclusivity_v1 import ReservationZone, SpatialReservationExclusivityV1


def test_stair_inside_parking_is_hard_failure():
    result=SpatialReservationExclusivityV1().evaluate([
        ReservationZone("S","stair","ground",[[0,0],[2,0],[2,2],[0,2]],("ground","first")),
        ReservationZone("P","parking_stall","ground",[[1,1],[3,1],[3,3],[1,3]])])
    assert result["hard_validation_status"]=="not_feasible"
    assert "stair_overlaps_parking_stall" in result["hard_failure_codes"]
    assert result["gate_position"]=="before_scoring"


def test_daylight_court_inside_vertical_core_is_cross_floor_hard_failure():
    result=SpatialReservationExclusivityV1().evaluate([
        ReservationZone("C","vertical_core","ground",[[0,0],[2,0],[2,2],[0,2]],("ground","first","second")),
        ReservationZone("D","daylight_court","first",[[1,1],[3,1],[3,3],[1,3]],("first","second"))])
    assert "daylight_court_overlaps_core" in result["hard_failure_codes"]
    assert result["collisions"][0]["collision_scope"]=="cross_floor_vertical"


def test_compatible_adjacent_or_disjoint_zones_pass():
    result=SpatialReservationExclusivityV1().evaluate([
        ReservationZone("S","stair","ground",[[0,0],[1,0],[1,1],[0,1]]),
        ReservationZone("P","parking_stall","ground",[[1,0],[2,0],[2,1],[1,1]]),
        ReservationZone("L","lobby","ground",[[0,0],[1,0],[1,1],[0,1]])])
    assert result["hard_validation_status"]=="hard_valid"
