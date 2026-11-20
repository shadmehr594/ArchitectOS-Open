import inspect
from shapely.affinity import rotate, translate
from shapely.geometry import Polygon

from core.architecture.reasoning.contextual_site_resource_map_v1 import ContextualSiteResourceMapV1
from core.architecture.reasoning.contextual_program_demand_profile_v1 import ContextualProgramDemandProfileV1
from core.architecture.reasoning.resource_scarcity_and_competition_v1 import ResourceScarcityAndCompetitionV1
from core.architecture.reasoning.contextual_spatial_allocation_planner_v1 import ContextualSpatialAllocationPlannerV1
from core.architecture.reasoning.pre_realization_daylight_deficit_v1 import PreRealizationDaylightDeficitV1
from core.architecture.reasoning.contextual_allocation_geometry_realizer_v1 import ContextualAllocationGeometryRealizerV1


def evidence(value): return {"value":value,"status":"known","source":"synthetic_observation","provenance":["fixture"],"confidence":.9}


def resource(rid, polygon, capacity, light, public=.5, terrace=.5):
    values={"frontage_value":public,"public_access_value":public,"daylight_value":light,"visibility_value":public,
            "privacy_value":1-public,"quietness_value":1-public,"terrace_value":terrace,"commercial_value":public}
    return {"resource_id":rid,"geometry":polygon,"floor_scope":["level-a","level-b"],"usable_capacity":capacity,
            "evidence_kind":"measured_exposure","channels":{k:evidence(v) for k,v in values.items()}}


def function(fid, kind, area, floors=("level-a",), prerequisites=()):
    return {"function_id":fid,"function":kind,"required_capacity":area,"floor_scope":list(floors),"prerequisites":list(prerequisites)}


def contracts(light=.15, include_source=True):
    regions=[resource("exposed",Polygon([(0,0),(12,0),(12,5),(0,5)]),60,light,.9,.9),
             resource("sheltered",Polygon([(0,5),(12,5),(12,12),(0,12)]),84,.1,.15,.1)]
    funcs=[function("shop","commercial",14),function("living","living",18,("level-b",)),
           function("terrace","terrace",6,("level-b",)),function("stair","stair",5,("level-a","level-b")),
           function("elevator","elevator",3,("level-a","level-b")),function("lobby","lobby",6,("level-a","level-b")),
           function("parking","parking",15),function("vehicle-field","vehicle_circulation",20),
           function("walk","pedestrian_access",4)]
    if include_source: funcs.append(function("new-light","daylight_source",5,("level-b",)))
    rm=ContextualSiteResourceMapV1().build({"floors":["level-a","level-b"],"resource_regions":regions})
    dp=ContextualProgramDemandProfileV1().build({"functions":funcs,"demands":{"parking":{},"vehicle_circulation":{},"pedestrian_access":{},"daylight_source":{}}})
    # Unknown implementation roles are supplied explicit demands rather than receiving invented defaults.
    for f in dp["functions"]:
        if f["function"] in ("parking","vehicle_circulation","pedestrian_access","daylight_source"):
            f["status"]="known"
            for item in f["demands"].values(): item.update({"value":.1,"status":"known","source":"fixture","provenance":["fixture"],"confidence":.8})
    sc=ResourceScarcityAndCompetitionV1().evaluate(rm,dp)
    plan=ContextualSpatialAllocationPlannerV1().plan(rm,dp,sc,max_hypotheses=5)
    deficit=PreRealizationDaylightDeficitV1().evaluate(rm,dp)
    floors={"level-a":[(0,0),(12,0),(12,12),(0,12)],"level-b":[(0,0),(12,0),(12,12),(0,12)]}
    return rm,dp,sc,plan,deficit,floors


def test_pre_geometry_deficit_publishes_supply_competition_and_source_requirements():
    rm,dp,_,_,deficit,_=contracts(light=.02)
    assert deficit["demonstrated_deficits"] and deficit["additional_daylight_source_required"]
    assert deficit["new_source_requirements"]["location_status"]=="not_determined"
    assert all("competing_functions" in x and "confidence" in x and "provenance" in x for x in deficit["demonstrated_deficits"])
    assert not deficit["court_assumed"]


def test_existing_capacity_can_prove_no_additional_source_is_needed():
    rm,dp,_,_,_,_=contracts(light=1,include_source=False)
    deficit=PreRealizationDaylightDeficitV1().evaluate(rm,dp)
    assert not deficit["additional_daylight_source_required"] and deficit["new_source_requirements"] is None


def test_realizer_consumes_joint_hypotheses_and_preserves_multiple_alternatives():
    rm,dp,_,plan,deficit,floors=contracts()
    result=ContextualAllocationGeometryRealizerV1().realize(plan,rm,dp,deficit,floors)
    assert len(plan["hypotheses"])>1 and len(result["candidates"])==len(plan["hypotheses"])
    assert all(not c["geometry_seed_used"] and not c["final_selection_performed"] for c in result["candidates"])


def test_infeasible_ownership_skips_contextual_evaluation_and_shortlist():
    rm,dp,_,plan,deficit,floors=contracts(); calls=[]
    bad=dict(plan); bad["hypotheses"]=[{"hypothesis_id":"over-capacity","assignments":[
        {"function_id":"shop","resource_id":"exposed","consumed_capacity":55,"utility":1,"evidence":[]},
        {"function_id":"parking","resource_id":"exposed","consumed_capacity":55,"utility":1,"evidence":[]}],"prerequisites":{}}]
    result=ContextualAllocationGeometryRealizerV1().realize(bad,rm,dp,deficit,floors,lambda *x:calls.append(x))
    assert result["shortlist"]==[] and result["candidates"][0]["contextual_scoring_skipped"] and calls==[]


def test_terrace_geometry_follows_assigned_resource():
    rm,dp,_,plan,deficit,floors=contracts(); hypothesis={"hypothesis_id":"terrace-proof","assignments":[
        {"function_id":"terrace","resource_id":"sheltered","consumed_capacity":6,"utility":1,"evidence":["fixture"]}],"prerequisites":{}}
    out=ContextualAllocationGeometryRealizerV1().realize({"hypotheses":[hypothesis]},rm,dp,deficit,floors)
    terrace=Polygon(out["candidates"][0]["geometry"][0]["polygon"])
    assert Polygon([(0,5),(12,5),(12,12),(0,12)]).covers(terrace)


def test_new_source_geometry_requires_demonstrated_deficit():
    rm,dp,_,plan,_,floors=contracts(light=1)
    no_deficit=PreRealizationDaylightDeficitV1().evaluate(rm,dp)
    hypothesis={"hypothesis_id":"unsupported-source","assignments":[{"function_id":"new-light","resource_id":"sheltered","consumed_capacity":5,"utility":1,"evidence":[]}],"prerequisites":{}}
    out=ContextualAllocationGeometryRealizerV1().realize({"hypotheses":[hypothesis]},rm,dp,no_deficit,floors)
    assert out["candidates"][0]["hard_validation_status"]=="not_feasible"
    assert "daylight_source_without_demonstrated_deficit" in out["candidates"][0]["hard_rejection_reasons"]


def test_no_unauthorized_positive_area_overlap_survives():
    rm,dp,_,plan,deficit,floors=contracts(); out=ContextualAllocationGeometryRealizerV1().realize(plan,rm,dp,deficit,floors)
    for candidate in out["candidates"]:
        assert "double_ownership_overlap" not in candidate["floor_program_ownership"]["hard_failure_codes"]


def test_vertical_components_share_required_scope_and_core_is_continuous():
    rm,dp,_,plan,deficit,floors=contracts(); out=ContextualAllocationGeometryRealizerV1().realize(plan,rm,dp,deficit,floors)
    candidate=next(c for c in out["candidates"] if c["floor_program_ownership"]["hard_validation_status"]=="hard_valid" and {"stair","elevator","lobby"}.issubset({g["space_id"] for g in c["geometry"]}))
    records=candidate["floor_program_ownership"]["spaces"]
    vertical=[r for r in records if r["space_id"] in ("stair","elevator","lobby","VERTICAL-CORE")]
    assert all(r["floor_scope"]==["level-a","level-b"] and r["vertical_extent"].startswith("CONTINUOUS:") for r in vertical)


def test_assignment_change_regenerates_a_different_fingerprint():
    rm,dp,_,_,deficit,floors=contracts(); base={"hypothesis_id":"one","assignments":[{"function_id":"shop","resource_id":"exposed","consumed_capacity":14,"utility":1,"evidence":[]}],"prerequisites":{}}
    changed={**base,"hypothesis_id":"two","assignments":[{**base["assignments"][0],"resource_id":"sheltered"}]}
    out=ContextualAllocationGeometryRealizerV1().realize({"hypotheses":[base,changed]},rm,dp,deficit,floors)
    assert out["candidates"][0]["realization_fingerprint"]!=out["candidates"][1]["realization_fingerprint"]


def test_rigid_transform_preserves_intrinsic_allocation_geometry():
    # Geometry choices depend on intrinsic resource geometry, not a global axis.
    rm,dp,_,_,deficit,floors=contracts(); base={"hypothesis_id":"a","assignments":[{"function_id":"shop","resource_id":"exposed","consumed_capacity":14,"utility":1,"evidence":[]}],"prerequisites":{}}
    first=ContextualAllocationGeometryRealizerV1().realize({"hypotheses":[base]},rm,dp,deficit,floors)["candidates"][0]
    transformed=[]
    for r in rm["resources"]:
        g=translate(rotate(Polygon(r["geometry"]["coordinates"][0]),37,origin=(0,0)),21,-8); item=dict(r); item["geometry"]=g.__geo_interface__; transformed.append(item)
    transformed_floors={k:list(translate(rotate(Polygon(v),37,origin=(0,0)),21,-8).exterior.coords)[:-1] for k,v in floors.items()}
    second=ContextualAllocationGeometryRealizerV1().realize({"hypotheses":[base]},{**rm,"resources":transformed},dp,deficit,transformed_floors)["candidates"][0]
    assert abs(sum(Polygon(x["polygon"]).area for x in first["geometry"])-sum(Polygon(x["polygon"]).area for x in second["geometry"]))<1e-6


def test_source_audit_has_no_forbidden_generation_shortcuts():
    from core.architecture.reasoning import pre_realization_daylight_deficit_v1 as a
    from core.architecture.reasoning import contextual_allocation_geometry_realizer_v1 as b
    source=(inspect.getsource(a)+inspect.getsource(b)).lower()
    directions=["".join(x) for x in (("n","o","r","t","h"),("e","a","s","t"),("s","o","u","t","h"),("w","e","s","t"))]
    families=["".join(x) for x in (("h","y","b","r","i","d"),("n","s"),("e","w"))]
    assert not any(('"'+x+'"') in source or ("'"+x+"'") in source for x in directions+families)
    assert "parcel"+" 2" not in source and "parcel"+"2" not in source


def test_state_flags_remain_nonfinal_and_nonexecutional():
    rm,dp,_,plan,deficit,floors=contracts(); out=ContextualAllocationGeometryRealizerV1().realize(plan,rm,dp,deficit,floors)
    assert out["final_selection_performed"] is False and out["winner"] is None
    assert all(not c[k] for c in out["candidates"] for k in ("room_layout_generated","final_windows_generated","structure_executed","bim_executed","ifc_executed","render_executed"))
