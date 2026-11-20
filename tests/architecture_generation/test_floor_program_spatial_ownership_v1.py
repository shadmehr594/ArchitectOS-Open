from shapely.geometry import box

from core.architecture.reasoning.floor_program_spatial_ownership_v1 import (
    FloorProgramSpatialOwnershipV1, OwnershipSpace)


ROLES=FloorProgramSpatialOwnershipV1.ROLES


def record(space_id, role, polygon, floors=("ground",), extent="SINGLE_FLOOR", may=()):
    return OwnershipSpace(space_id, floors, extent, role, polygon,
        tuple(sorted(ROLES-{role}-set(may))), tuple(may), "synthetic_requirement")


def test_cross_floor_ownership_only_collides_on_shared_floor_scope():
    ledger=FloorProgramSpatialOwnershipV1()
    boundary={"ground":list(box(0,0,10,10).exterior.coords)[:-1],"first":list(box(0,0,10,10).exterior.coords)[:-1]}
    spaces=[record("GROUND-SHOP","COMMERCIAL",list(box(0,0,5,5).exterior.coords)[:-1]),
            record("FIRST-UNIT","RESIDENTIAL_UNIT",list(box(0,0,5,5).exterior.coords)[:-1],("first",))]
    result=ledger.evaluate(boundary,spaces)
    assert "double_ownership_overlap" not in result["hard_failure_codes"]


def test_commercial_core_overlap_is_fail_closed():
    boundary={"ground":list(box(0,0,10,10).exterior.coords)[:-1],"first":list(box(0,0,10,10).exterior.coords)[:-1]}
    core=list(box(1,1,4,4).exterior.coords)[:-1]
    result=FloorProgramSpatialOwnershipV1().evaluate(boundary,[
        record("CORE","VERTICAL_CORE",core,("ground","first"),"CONTINUOUS:ground..first"),
        record("SHOP","COMMERCIAL",list(box(2,2,6,6).exterior.coords)[:-1])])
    assert result["hard_validation_status"]=="not_feasible"
    assert "ownership_overlap_not_explicitly_allowed" in result["hard_failure_codes"]


def test_residential_level_daylight_void_does_not_occupy_ground():
    court=record("COURT","DAYLIGHT_COURT",list(box(2,2,4,4).exterior.coords)[:-1],("first","second"),"RESIDENTIAL_LEVEL_DAYLIGHT_VOID")
    result=FloorProgramSpatialOwnershipV1().evaluate({f:list(box(0,0,10,10).exterior.coords)[:-1] for f in ("ground","first","second")},[court])
    assert "COURT" not in result["floors"]["ground"]
    assert "COURT" in result["floors"]["first"] and "COURT" in result["floors"]["second"]


def test_full_height_daylight_court_explicitly_occupies_ground_and_residential_floors():
    floors=("ground","first","second")
    court=record("COURT","DAYLIGHT_COURT",list(box(2,2,4,4).exterior.coords)[:-1],floors,"FULL_HEIGHT_DAYLIGHT_COURT")
    result=FloorProgramSpatialOwnershipV1().evaluate({f:list(box(0,0,10,10).exterior.coords)[:-1] for f in floors},[court])
    assert all("COURT" in result["floors"][floor] for floor in floors)


def test_double_ownership_without_mutual_allowlist_fails():
    boundary={"ground":list(box(0,0,10,10).exterior.coords)[:-1]}
    result=FloorProgramSpatialOwnershipV1().evaluate(boundary,[
        record("A","COMMERCIAL",list(box(0,0,6,6).exterior.coords)[:-1]),
        record("B","SERVICE",list(box(5,5,8,8).exterior.coords)[:-1])])
    assert "double_ownership_overlap" in result["hard_failure_codes"]


def test_vertical_continuity_requires_multifloor_continuous_extent():
    boundary={"ground":list(box(0,0,10,10).exterior.coords)[:-1]}
    result=FloorProgramSpatialOwnershipV1().evaluate(boundary,[record("STAIR","STAIR",list(box(0,0,2,2).exterior.coords)[:-1])])
    assert "vertical_continuity_missing" in result["hard_failure_codes"]


def test_unallocated_residual_accounting_balances_exactly():
    boundary={"ground":list(box(0,0,10,10).exterior.coords)[:-1]}
    result=FloorProgramSpatialOwnershipV1().evaluate(boundary,[
        record("SHOP","COMMERCIAL",list(box(0,0,6,10).exterior.coords)[:-1]),
        record("UNALLOCATED","UNALLOCATED",list(box(6,0,10,10).exterior.coords)[:-1])])
    assert result["area_accounting"]["ground"]["balanced"]
    assert result["area_accounting"]["ground"]["computed_unallocated_area"]==40


def test_residual_mismatch_is_a_hard_failure():
    boundary={"ground":list(box(0,0,10,10).exterior.coords)[:-1]}
    result=FloorProgramSpatialOwnershipV1().evaluate(boundary,[
        record("SHOP","COMMERCIAL",list(box(0,0,6,10).exterior.coords)[:-1]),
        record("UNALLOCATED","UNALLOCATED",list(box(6,0,8,10).exterior.coords)[:-1])])
    assert result["hard_validation_status"]=="not_feasible"
    assert "residual_accounting_mismatch" in result["hard_failure_codes"]


def test_missing_or_conflicting_policy_is_not_hard_valid():
    boundary={"ground":list(box(0,0,10,10).exterior.coords)[:-1]}
    missing=record("SHOP","COMMERCIAL",list(box(0,0,2,2).exterior.coords)[:-1]).as_dict()
    missing["exclusive_with"]=[]
    conflict=record("SERVICE","SERVICE",list(box(3,0,5,2).exterior.coords)[:-1]).as_dict()
    conflict["may_overlap_with"]=["COMMERCIAL"]
    assert FloorProgramSpatialOwnershipV1().evaluate(boundary,[missing])["hard_validation_status"]=="not_feasible"
    result=FloorProgramSpatialOwnershipV1().evaluate(boundary,[conflict])
    assert "ownership_policy_conflict" in result["hard_failure_codes"]


def test_lobby_requires_continuous_multifloor_scope():
    boundary={"ground":list(box(0,0,10,10).exterior.coords)[:-1]}
    result=FloorProgramSpatialOwnershipV1().evaluate(boundary,[record("LOBBY","LOBBY",list(box(0,0,2,2).exterior.coords)[:-1])])
    assert "vertical_continuity_missing" in result["hard_failure_codes"]
