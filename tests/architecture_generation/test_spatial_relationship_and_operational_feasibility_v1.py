import inspect
from shapely.affinity import rotate, translate
from shapely.geometry import LineString, Polygon

from core.architecture.reasoning.spatial_relationship_and_operational_feasibility_v1 import SpatialRelationshipAndOperationalFeasibilityV1


def space(sid, coords, role="COMMON", floors=("level-1",)):
    return {"space_id":sid,"polygon":coords,"occupancy_role":role,"floor_scope":list(floors)}


def relation(kind,left,right,via=(),**extra):
    return {"relationship_id":"%s-%s-%s"%(kind,left,right),"relationship":kind,"from":left,"to":right,
            "via":list(via),"required":True,"provenance":["synthetic_requirement"],"confidence":.95,**extra}


def evaluate(spaces, relationships, daylight=None, ownership=None):
    return SpatialRelationshipAndOperationalFeasibilityV1().evaluate(spaces,relationships,daylight,ownership or {"hard_validation_status":"hard_valid"})


def test_unreachable_stall_fails_despite_non_overlap():
    spaces=[space("entry",[(0,0),(1,0),(1,1),(0,1)],"VEHICLE_CIRCULATION"),space("field",[(1,0),(5,0),(5,2),(1,2)],"VEHICLE_CIRCULATION"),space("stall",[(7,0),(9,0),(9,2),(7,2)],"PARKING_STALL")]
    out=evaluate(spaces,[relation("VEHICLE_ACCESSIBLE_FROM","entry","stall",("field",))])
    assert out["hard_validation_status"]=="not_feasible"


def test_connected_vehicle_field_serves_every_stall():
    spaces=[space("entry",[(0,0),(1,0),(1,1),(0,1)],"VEHICLE_CIRCULATION"),space("field",[(1,0),(7,0),(7,3),(1,3)],"VEHICLE_CIRCULATION"),space("p1",[(7,0),(9,0),(9,1),(7,1)],"PARKING_STALL"),space("p2",[(7,1),(9,1),(9,2),(7,2)],"PARKING_STALL")]
    out=evaluate(spaces,[relation("VEHICLE_ACCESSIBLE_FROM","entry",x,("field",)) for x in ("p1","p2")])
    assert out["hard_validation_status"]=="hard_valid" and all(r["geometry_evidence"]["network_connected"] for r in out["relationship_results"])


def commercial_fixture(blocked):
    spaces=[space("outside",[(0,0),(1,0),(1,1),(0,1)]),space("route",[(1,0),(6,0),(6,1),(1,1)],"PEDESTRIAN_ACCESS"),space("shop",[(6,0),(9,0),(9,4),(6,4)],"COMMERCIAL")]
    path=[(.5,.5),(7,.5)]
    if blocked: spaces.append(space("private",[(3,-1),(4,-1),(4,2),(3,2)],"RESIDENTIAL_UNIT"))
    rels=[relation("CONNECTED_BY_CIRCULATION","outside","shop",("route",)),relation("MUST_NOT_REQUIRE_TRANSIT_THROUGH","outside","shop",path_geometry=path,forbidden=["private"] if blocked else [])]
    return spaces,rels


def test_commercial_access_crossing_incompatible_zone_fails():
    spaces,rels=commercial_fixture(True); out=evaluate(spaces,rels)
    assert out["hard_validation_status"]=="not_feasible" and "route_crosses_incompatible_zone" in out["hard_failure_codes"]


def test_commercial_access_with_valid_public_route_passes():
    spaces,rels=commercial_fixture(False); assert evaluate(spaces,rels)["hard_validation_status"]=="hard_valid"


def test_ownership_valid_core_can_fail_operational_connection():
    spaces=[space("common",[(0,0),(2,0),(2,2),(0,2)]),space("lobby",[(4,0),(6,0),(6,2),(4,2)],"LOBBY"),space("stair",[(6,0),(8,0),(8,2),(6,2)],"STAIR"),space("lift",[(6,2),(8,2),(8,4),(6,4)],"ELEVATOR")]
    rels=[relation("DIRECT_ACCESS","common","lobby"),relation("DIRECT_ACCESS","lobby","stair"),relation("DIRECT_ACCESS","lobby","lift")]
    assert evaluate(spaces,rels)["hard_validation_status"]=="not_feasible"


def test_vertical_alignment_is_geometry_and_scope_based():
    a=space("a",[(0,0),(2,0),(2,2),(0,2)],"STAIR",("level-1","level-2")); b=space("b",[(0,0),(2,0),(2,2),(0,2)],"STAIR",("level-1","level-2")); c=space("c",[(1,0),(3,0),(3,2),(1,2)],"STAIR",("level-1","level-2"))
    assert evaluate([a,b],[relation("VERTICALLY_ALIGNED_WITH","a","b")])["hard_validation_status"]=="hard_valid"
    assert evaluate([a,c],[relation("VERTICALLY_ALIGNED_WITH","a","c")])["hard_validation_status"]=="not_feasible"
    mismatched={**b,"floor_scope":["level-1"]}
    assert evaluate([a,mismatched],[relation("VERTICALLY_ALIGNED_WITH","a","b",required_floor_scope=["level-1","level-2"])])["hard_validation_status"]=="not_feasible"


def daylight_fixture(served):
    source=[(3,0),(5,0),(5,4),(3,4)] if served else [(8,0),(10,0),(10,4),(8,4)]
    spaces=[space("living",[(0,0),(3,0),(3,4),(0,4)],"RESIDENTIAL_UNIT"),space("court",source,"DAYLIGHT_COURT"),space("link",[(3,1),(5 if served else 6,1),(5 if served else 6,2),(3,2)],"COMMON")]
    deficit={"demonstrated_deficits":[{"function_id":"living"}]}
    return spaces,[relation("REQUIRES_DAYLIGHT_FROM","living","court",("link",))],deficit


def test_daylight_source_not_serving_deficient_zone_fails():
    spaces,rels,deficit=daylight_fixture(False); assert evaluate(spaces,rels,deficit)["hard_validation_status"]=="not_feasible"


def test_daylight_source_serving_demonstrated_deficit_passes():
    spaces,rels,deficit=daylight_fixture(True); assert evaluate(spaces,rels,deficit)["hard_validation_status"]=="hard_valid"


def test_terrace_without_owner_access_fails():
    spaces=[space("unit",[(0,0),(3,0),(3,3),(0,3)],"RESIDENTIAL_UNIT"),space("terrace",[(5,0),(7,0),(7,2),(5,2)],"TERRACE")]
    assert evaluate(spaces,[relation("DIRECT_ACCESS","unit","terrace")])["hard_validation_status"]=="not_feasible"


def test_private_unit_transit_is_rejected():
    spaces=[space("unit-a",[(0,0),(3,0),(3,3),(0,3)],"RESIDENTIAL_UNIT"),space("unit-b",[(3,0),(6,0),(6,3),(3,3)],"RESIDENTIAL_UNIT"),space("common",[(6,0),(8,0),(8,3),(6,3)])]
    rel=relation("MUST_NOT_REQUIRE_TRANSIT_THROUGH","unit-a","common",path_geometry=[(1,1),(7,1)],forbidden=["unit-b"])
    assert evaluate(spaces,[rel])["hard_validation_status"]=="not_feasible"


def test_rigid_transform_preserves_relationship_decisions():
    spaces,rels=commercial_fixture(False); first=evaluate(spaces,rels)
    transformed=[]
    for item in spaces:
        g=translate(rotate(Polygon(item["polygon"]),31,origin=(0,0)),13,-4); transformed.append({**item,"polygon":list(g.exterior.coords)[:-1]})
    transformed_rels=[]
    for rel in rels:
        item=dict(rel)
        if item.get("path_geometry"):
            g=translate(rotate(LineString(item["path_geometry"]),31,origin=(0,0)),13,-4); item["path_geometry"]=list(g.coords)
        transformed_rels.append(item)
    second=evaluate(transformed,transformed_rels)
    assert [x["status"] for x in first["relationship_results"]]==[x["status"] for x in second["relationship_results"]]


def test_geometry_change_updates_operational_fingerprint():
    spaces,rels=commercial_fixture(False); first=evaluate(spaces,rels)
    moved=[dict(x) for x in spaces]; moved[-1]={**moved[-1],"polygon":[(8,0),(11,0),(11,4),(8,4)]}
    second=evaluate(moved,rels)
    assert first["operational_fingerprint"]!=second["operational_fingerprint"] and second["hard_validation_status"]=="not_feasible"


def test_ownership_failure_skips_operational_gate():
    out=evaluate([],[],ownership={"hard_validation_status":"not_feasible"})
    assert out["status"]=="skipped_upstream_ownership_failure" and out["operational_scoring_skipped"] and out["critic_skipped"]


def test_operational_failure_cannot_reach_downstream_evaluation():
    spaces,rels=commercial_fixture(True); out=evaluate(spaces,rels)
    assert out["hard_validation_status"]=="not_feasible" and out["operational_scoring_skipped"] and out["critic_skipped"]


def test_realizer_enforces_operational_gate_before_contextual_callback():
    from core.architecture.reasoning.contextual_allocation_geometry_realizer_v1 import ContextualAllocationGeometryRealizerV1
    resource={"contract":"ContextualSiteResourceMapV1","resources":[{"resource_id":"zone","geometry":Polygon([(0,0),(8,0),(8,4),(0,4)]).__geo_interface__}]}
    demand={"functions":[{"function_id":"shop","function":"commercial","floor_scope":["level-1"]}]}
    plan={"hypotheses":[{"hypothesis_id":"candidate","assignments":[{"function_id":"shop","resource_id":"zone","consumed_capacity":8,"evidence":[]}],"prerequisites":{}}]}
    calls=[]; floors={"level-1":[(0,0),(8,0),(8,4),(0,4)]}
    out=ContextualAllocationGeometryRealizerV1().realize(plan,resource,demand,{"demonstrated_deficits":[]},floors,lambda *x:calls.append(x),[])
    assert out["shortlist"]==[] and calls==[] and out["candidates"][0]["contextual_scoring_skipped"]


def test_contract_source_has_no_generation_shortcuts():
    import core.architecture.reasoning.spatial_relationship_and_operational_feasibility_v1 as module
    source=inspect.getsource(module).lower(); compass=["".join(x) for x in (("n","o","r","t","h"),("e","a","s","t"),("s","o","u","t","h"),("w","e","s","t"))]
    families=["".join(x) for x in (("n","s"),("e","w"),("h","y","b","r","i","d"))]
    assert not any(('"'+x+'"') in source or ("'"+x+"'") in source for x in compass+families)
    assert "parcel"+"2" not in source and "parcel"+" 2" not in source
