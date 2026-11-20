import inspect

from core.architecture.reasoning.operational_relationship_requirement_derivation_v1 import OperationalRelationshipRequirementDerivationV1
from core.architecture.reasoning.contextual_allocation_geometry_realizer_v1 import ContextualAllocationGeometryRealizerV1
from core.architecture.reasoning.spatial_relationship_and_operational_feasibility_v1 import SpatialRelationshipAndOperationalFeasibilityV1
from core.architecture.reasoning.architectural_design_intelligence_v1 import TopologyInvalidationEngine


def fn(fid,kind,floors=("a",),owner=None):
    operational={}
    if owner: operational["owner_function_id"]=owner
    return {"function_id":fid,"function":kind,"floor_scope":list(floors),"operational_requirements":operational}


def derive(functions, daylight=None, allocated=None, requirements=None):
    allocated=allocated or [x["function_id"] for x in functions]
    plan={"hypotheses":[{"hypothesis_id":"h","assignments":[{"function_id":x,"resource_id":"r"} for x in allocated]}]}
    return OperationalRelationshipRequirementDerivationV1().derive({"functions":functions},plan,daylight or {"floors":[]},requirements or {"provenance":["synthetic_program"],"confidence":.9})


def relationships(result): return result["hypotheses"][0]["relationship_requirements"]
def unresolved(result): return result["hypotheses"][0]["unresolved_requirements"]


def test_parking_derives_vehicle_circulation_and_site_access_requirements():
    out=derive([fn("p","parking"),fn("field","vehicle_circulation"),fn("gate","site_vehicle_entrance")])
    pairs={(x["source_function"],x["relationship_type"],x["target_function"]) for x in relationships(out)}
    assert ("p","VEHICLE_ACCESSIBLE_FROM","field") in pairs
    assert ("field","CONNECTED_BY_CIRCULATION","gate") in pairs


def test_commercial_derives_public_access_via_public_circulation():
    out=derive([fn("shop","commercial"),fn("walk","pedestrian_access"),fn("door","public_pedestrian_entrance")])
    item=next(x for x in relationships(out) if x["source_function"]=="shop")
    assert item["relationship_type"]=="CONNECTED_BY_CIRCULATION" and item["via_functions"]==["walk"]


def test_core_connectivity_and_vertical_scope_are_derived():
    floors=("a","b","c"); out=derive([fn("lobby","lobby",floors),fn("stair","stair",floors),fn("lift","elevator",floors)])
    items=relationships(out); core={(x["source_function"],x["target_function"],x["relationship_type"]) for x in items}
    assert ("lobby","stair","DIRECT_ACCESS") in core and ("lobby","lift","DIRECT_ACCESS") in core
    vertical=[x for x in items if x["relationship_type"]=="VERTICALLY_ALIGNED_WITH"]
    assert {tuple(x["floor_scope"]) for x in vertical}=={floors}


def test_terrace_without_owner_is_mandatory_unresolved():
    out=derive([fn("deck","terrace")]); missing=out["hypotheses"][0]["mandatory_unresolved"]
    assert any(x["source_function"]=="deck" and x["reason"]=="required_target_not_defined" for x in missing)


def test_residential_route_has_private_transit_prohibition():
    out=derive([fn("unit","residential_unit"),fn("other","residential_unit"),fn("hall","common")])
    assert any(x["relationship_type"]=="CONNECTED_BY_CIRCULATION" for x in relationships(out))
    constraint=next(x for x in relationships(out) if x["relationship_type"]=="MUST_NOT_REQUIRE_TRANSIT_THROUGH" and x["source_function"]=="unit")
    assert "private" in constraint["forbidden_zones"]
    assert constraint["via_functions"]==["hall"] and constraint["forbidden_functions"]==["other"]


def test_realizer_binds_allocated_route_and_forbidden_geometry_without_inference():
    contract=derive([fn("unit","residential_unit"),fn("other","residential_unit"),fn("hall","common")])
    generated=[{"space_id":"unit","polygon":[[0,0],[1,0],[1,1],[0,1]]},
        {"space_id":"other","polygon":[[2,0],[3,0],[3,1],[2,1]]},
        {"space_id":"hall","polygon":[[0,1],[3,1],[3,2],[0,2]]}]
    bound=ContextualAllocationGeometryRealizerV1._relationships_for_hypothesis(contract,"h",generated)
    relation=next(x for x in bound if x["relationship"]=="MUST_NOT_REQUIRE_TRANSIT_THROUGH" and x["from"]=="unit")
    assert relation["path_geometry"]==generated[2]["polygon"] and relation["forbidden"]==["other"]


def daylight(state):
    return {"floors":[{"floor":"a","evidence_state":state}],"demonstrated_deficits":[{"function_id":"living","floor":"a","confidence":.8}] if state=="KNOWN_DEFICIT" else []}


def test_known_deficit_can_create_daylight_requirement():
    out=derive([fn("living","living"),fn("light","daylight_source")],daylight("KNOWN_DEFICIT"))
    assert any(x["relationship_type"]=="REQUIRES_DAYLIGHT_FROM" for x in relationships(out))


def test_unknown_or_incomplete_daylight_never_creates_source_requirement():
    for state in ("UNKNOWN_SUPPLY","INCOMPLETE_EVIDENCE"):
        out=derive([fn("living","living"),fn("light","daylight_source")],daylight(state))
        assert not any(x.get("relationship_type")=="REQUIRES_DAYLIGHT_FROM" for x in relationships(out)+unresolved(out))


def test_missing_mandatory_target_is_unresolved_without_fabrication():
    out=derive([fn("p","parking")]); item=next(x for x in unresolved(out) if x["source_function"]=="p")
    assert item["target_function"] is None and item["status"]=="unresolved" and not out["complete"]


def test_optional_missing_target_does_not_make_contract_incomplete():
    req={"provenance":["synthetic"],"relationship_overrides":{"commercial.public_access":{"required":False}}}
    out=derive([fn("shop","commercial")],requirements=req)
    item=next(x for x in unresolved(out) if x["source_function"]=="shop")
    assert item["optional"] and out["complete"]


def test_coordinate_transform_cannot_change_non_geometric_derivation():
    functions=[fn("p","parking"),fn("field","vehicle_circulation"),fn("gate","site_vehicle_entrance")]
    first=derive(functions); second=derive(functions,requirements={"provenance":["synthetic_program"],"confidence":.9,"coordinate_transform":{"rotation":41,"translation":[9,-3]}})
    normalize=lambda out:[(x["relationship_type"],x["source_function"],x.get("target_function"),x["status"]) for x in relationships(out)]
    assert normalize(first)==normalize(second)


def test_ownership_invalid_skips_operational_engine():
    out=SpatialRelationshipAndOperationalFeasibilityV1().evaluate([],[],ownership={"hard_validation_status":"not_feasible"})
    assert out["status"]=="skipped_upstream_ownership_failure" and out["operational_scoring_skipped"]


def test_operational_invalid_is_marked_to_skip_context_and_critic():
    spaces=[{"space_id":"a","polygon":[(0,0),(1,0),(1,1),(0,1)]},{"space_id":"b","polygon":[(3,0),(4,0),(4,1),(3,1)]}]
    rel=[{"relationship":"DIRECT_ACCESS","from":"a","to":"b","required":True,"provenance":["synthetic"],"confidence":1}]
    out=SpatialRelationshipAndOperationalFeasibilityV1().evaluate(spaces,rel,ownership={"hard_validation_status":"hard_valid"})
    assert out["hard_validation_status"]=="not_feasible" and out["operational_scoring_skipped"] and out["critic_skipped"]


def test_program_access_and_daylight_changes_update_fingerprint_and_invalidation():
    functions=[fn("shop","commercial"),fn("walk","pedestrian_access"),fn("door","public_pedestrian_entrance")]
    a=derive(functions); b=derive(functions,daylight("KNOWN_DEFICIT")); c=derive(functions,requirements={"provenance":["changed_access"],"confidence":.7})
    assert len({x["relationship_requirement_fingerprint"] for x in (a,b,c)})==3
    for trigger in ("program","requirements","daylight_deficit"):
        impact=TopologyInvalidationEngine().analyze([{"element_type":trigger,"floor":"a"}],["a","b"])
        assert {"operational_relationship_requirements","geometry_realization","operational_feasibility","decision_support_shortlist"}.issubset(impact["invalidated_dependencies"])


def test_source_scan_contains_no_project_or_generation_shortcuts():
    import core.architecture.reasoning.operational_relationship_requirement_derivation_v1 as module
    source=inspect.getsource(module).lower(); compass=["".join(x) for x in (("n","o","r","t","h"),("e","a","s","t"),("s","o","u","t","h"),("w","e","s","t"))]
    family=["".join(x) for x in (("n","s"),("e","w"),("h","y","b","r","i","d"))]
    assert not any(('"'+x+'"') in source or ("'"+x+"'") in source for x in compass+family)
    assert "parcel"+"2" not in source and "parcel"+" 2" not in source
