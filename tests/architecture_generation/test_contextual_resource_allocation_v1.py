import inspect
from shapely.geometry import LineString, Polygon

from core.architecture.reasoning.contextual_site_resource_map_v1 import ContextualSiteResourceMapV1
from core.architecture.reasoning.contextual_program_demand_profile_v1 import ContextualProgramDemandProfileV1
from core.architecture.reasoning.resource_scarcity_and_competition_v1 import ResourceScarcityAndCompetitionV1
from core.architecture.reasoning.contextual_spatial_allocation_planner_v1 import ContextualSpatialAllocationPlannerV1
from core.architecture.reasoning.opportunity_cost_evaluator_v1 import OpportunityCostEvaluatorV1


def channel(value, source="synthetic"):
    return {"value": value, "source": source, "provenance": [source], "confidence": .95}


def region(rid, coords, capacity, frontage, daylight=.5, terrace=.4, access=.5, commercial=.5):
    values={"frontage_value":frontage,"public_access_value":access,"daylight_value":daylight,
            "visibility_value":frontage,"privacy_value":1-frontage,"quietness_value":1-frontage,
            "terrace_value":terrace,"commercial_value":commercial}
    return {"resource_id":rid,"geometry":Polygon(coords),"floor_scope":["ground"],"usable_capacity":capacity,
            "evidence_kind":"synthetic_edge_region","channels":{k:channel(v) for k,v in values.items()}}


def backbone(regions, functions):
    rm=ContextualSiteResourceMapV1().build({"floors":["ground"],"resource_regions":regions})
    dp=ContextualProgramDemandProfileV1().build({"functions":functions})
    sc=ResourceScarcityAndCompetitionV1().evaluate(rm,dp)
    plan=ContextualSpatialAllocationPlannerV1().plan(rm,dp,sc)
    cost=OpportunityCostEvaluatorV1().evaluate(plan,dp)
    return rm,dp,sc,plan,cost


def fn(fid, kind, cap=1, prereq=()):
    return {"function_id":fid,"function":kind,"floor_scope":["ground"],"required_capacity":cap,"prerequisites":list(prereq)}


def test_a_abundant_frontage_does_not_reject_core_on_frontage():
    _,_,sc,plan,_=backbone([region("edge",[(0,0),(10,0),(10,2),(0,2)],20,1)], [fn("core","stair",2),fn("shop","commercial",3)])
    assert next(x for x in sc["resources"] if x["resource_channel"]=="frontage_value")["scarcity_class"]=="abundant"
    assert any(a["function_id"]=="core" and a["resource_id"]=="edge" for h in plan["hypotheses"] for a in h["assignments"])


def test_b_scarce_frontage_prefers_lower_cost_core_allocation():
    regions=[region("front",[(0,0),(2,0),(2,1),(0,1)],2,1,commercial=1),region("inside",[(0,2),(5,2),(5,5),(0,5)],20,.05,commercial=.05)]
    _,_,sc,plan,_=backbone(regions,[fn("shop","commercial",2),fn("core","stair",2)])
    assert next(x for x in sc["resources"] if x["resource_channel"]=="frontage_value")["scarcity_class"]=="scarce"
    assert any({a["function_id"]:a["resource_id"] for a in h["assignments"]}.get("shop")=="front" and {a["function_id"]:a["resource_id"] for a in h["assignments"]}.get("core")=="inside" for h in plan["hypotheses"])


def test_c_context_change_without_direction_changes_allocation():
    funcs=[fn("shop","commercial",2),fn("core","stair",2)]
    a=backbone([region("alpha",[(0,0),(2,0),(2,1),(0,1)],2,1),region("beta",[(0,2),(4,2),(4,4),(0,4)],8,.1)],funcs)[3]
    b=backbone([region("alpha",[(0,0),(2,0),(2,1),(0,1)],2,.1),region("beta",[(0,2),(4,2),(4,4),(0,4)],8,1)],funcs)[3]
    def shop(plan): return next(a["resource_id"] for h in plan["hypotheses"] for a in h["assignments"] if a["function_id"]=="shop")
    assert shop(a)!=shop(b)


def test_d_living_and_bedroom_outcompete_wc_storage_for_daylight():
    _,_,sc,_,_=backbone([region("lit",[(0,0),(2,0),(2,2),(0,2)],2,.4,daylight=1)], [fn("living","living"),fn("bed","bedroom"),fn("wc","wc"),fn("store","storage")])
    row=next(x for x in sc["resources"] if x["resource_channel"]=="daylight_value")
    ranked=[x["function_id"] for x in row["competing_functions"]]
    assert ranked.index("living")<ranked.index("wc") and ranked.index("bed")<ranked.index("store")


def test_e_terrace_competes_and_opportunity_cost_is_visible():
    _,_,_,plan,cost=backbone([region("valuable",[(0,0),(2,0),(2,1),(0,1)],2,1,terrace=1,commercial=1),region("other",[(0,2),(5,2),(5,4),(0,4)],10,.2,.4,.2)], [fn("terrace","terrace",2),fn("living","living",2),fn("shop","commercial",2)])
    assert plan["multiple_hypotheses"] and cost["alternatives"]
    assert len({next((a["function_id"] for a in h["assignments"] if a["resource_id"]=="valuable"),None) for h in plan["hypotheses"]})>1


def test_f_ownership_invalid_is_never_shortlisted_and_scoring_skipped():
    from core.architecture.reasoning.architectural_brain_orchestrator_v1 import ArchitecturalBrainOrchestratorV1
    assert hasattr(ArchitecturalBrainOrchestratorV1,"_contextual_shortlist")
    result=ArchitecturalBrainOrchestratorV1()._contextual_shortlist([{"hypothesis_id":"great"}], {"hard_validation_status":"not_feasible"})
    assert result["shortlist"]==[] and result["contextual_scoring_skipped"]


def test_g_resource_context_change_cleanly_invalidates_dependents():
    from core.architecture.reasoning.architectural_design_intelligence_v1 import TopologyInvalidationEngine
    out=TopologyInvalidationEngine().analyze([{"element_type":"frontage","floor":"ground"}],["ground","upper"])
    assert out["topology_changed"] and not out["local_patch_allowed"]
    assert {"site_resource_map","scarcity_model","allocation_plan","placement","topology"}.issubset(out["invalidated_dependencies"])


def test_h_public_sources_have_no_direction_or_parcel_literals():
    classes=(ContextualSiteResourceMapV1,ContextualProgramDemandProfileV1,ResourceScarcityAndCompetitionV1,ContextualSpatialAllocationPlannerV1,OpportunityCostEvaluatorV1)
    source="\n".join(inspect.getsource(c).lower() for c in classes)
    assert "parcel2" not in source and "parcel 2" not in source
    assert not any(("\"%s\""%d) in source or ("'%s'"%d) in source for d in ("north","east","south","west"))
    assert all(x not in source for x in (".52",".48",".08"))


def test_i_unknown_and_provenance_are_explicit_and_fail_closed():
    rm=ContextualSiteResourceMapV1().build({"floors":["ground"],"resource_regions":[{"resource_id":"x","geometry":LineString([(0,0),(1,0)]),"floor_scope":["ground"]}]})
    dp=ContextualProgramDemandProfileV1().build({"functions":[fn("mystery","unrecognized")]})
    assert rm["resources"][0]["channels"]["frontage_value"]["status"]=="unknown"
    assert dp["functions"][0]["status"]=="unknown_function_fail_closed"
    sc=ResourceScarcityAndCompetitionV1().evaluate(rm,dp)
    assert all(x["status"]=="unknown" and x["confidence"]==0 for x in sc["resources"])
