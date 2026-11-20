import inspect
from shapely.affinity import rotate, translate
from shapely.geometry import LineString, Polygon

from core.architecture.reasoning.evidence_based_site_resource_region_derivation_v1 import EvidenceBasedSiteResourceRegionDerivationV1
from core.architecture.reasoning.contextual_site_resource_map_v1 import ContextualSiteResourceMapV1
from core.architecture.reasoning.contextual_program_demand_profile_v1 import ContextualProgramDemandProfileV1
from core.architecture.reasoning.pre_realization_daylight_deficit_v1 import PreRealizationDaylightDeficitV1


def edge(geometry, openness=.8, usable=.9):
    return {"evidence_id":"edge-a","geometry":geometry,"floor_scope":["level"],"is_frontage":True,
        "public_access_eligible":True,"openness":openness,"usable_fraction":usable,"source":"survey",
        "provenance":["survey.edge-a"],"confidence":.94}


def test_geometry_evidence_derivation_is_rotation_translation_invariant():
    parcel=Polygon([(0,0),(10,0),(10,8),(0,8)]); boundary=LineString([(0,0),(10,0)])
    first=EvidenceBasedSiteResourceRegionDerivationV1().derive(parcel,[edge(boundary)],["level"])
    moved_parcel=translate(rotate(parcel,43,origin=(0,0)),17,-6); moved_edge=translate(rotate(boundary,43,origin=(0,0)),17,-6)
    second=EvidenceBasedSiteResourceRegionDerivationV1().derive(moved_parcel,[edge(moved_edge)],["level"])
    a=ContextualSiteResourceMapV1().build(first); b=ContextualSiteResourceMapV1().build(second)
    assert [round(x["gross_capacity"],8) for x in a["resources"]]==[round(x["gross_capacity"],8) for x in b["resources"]]
    assert [[x["channels"][c]["status"] for c in a["channels"]] for x in a["resources"]]==[[x["channels"][c]["status"] for c in b["channels"]] for x in b["resources"]]
    assert not first["directional_fallback_used"] and not first["fixed_band_used"]


def test_derivation_preserves_unknown_channels_and_provenance():
    parcel=Polygon([(0,0),(7,0),(7,6),(0,6)]); result=EvidenceBasedSiteResourceRegionDerivationV1().derive(parcel,[edge(LineString([(0,0),(7,0)]))],["level"])
    record=result["resource_regions"][0]
    assert record["channels"]["privacy_value"]["status"]=="unknown"
    assert record["channels"]["daylight_value"]["provenance"]==["survey.edge-a"]
    assert result["resource_regions"][-1]["geometry"]["type"]=="Polygon"


def test_parking_is_known_and_carries_dimensional_operational_semantics():
    requirements={"source":"project_requirement","parking":{"minimum_count":4,"stall_width":2.4,"stall_depth":4.9,
        "aisle_width":5.2,"minimum_turning_radius":5.1}}
    profile=ContextualProgramDemandProfileV1().build({"functions":[{"function_id":"parking","function":"parking","floor_scope":["level"]}]},requirements)
    parking=profile["functions"][0]
    assert parking["status"]=="known" and parking["quantity"]==4
    assert parking["required_capacity"]==2.4*4.9 and parking["dimensional_requirements"]==[2.4,4.9]
    assert {"vehicle_access","vehicle_circulation","maneuvering_field"}.issubset(parking["operational_requirements"]["dependencies"])
    assert parking["operational_requirements"]["provenance"]==["project_requirement"]
    assert parking["demands"]["daylight_need"]["value"]==0


def demand():
    return ContextualProgramDemandProfileV1().build({"functions":[{"function_id":"living","function":"living","floor_scope":["level"],"required_capacity":20}]})


def map_with(resources):
    return ContextualSiteResourceMapV1().build({"floors":["level"],"resource_regions":resources})


def daylight_resource(rid, capacity, value, status="known"):
    return {"resource_id":rid,"geometry":LineString([(0,0),(capacity,0)]),"floor_scope":["level"],"usable_capacity":capacity,
        "channels":{"daylight_value":{"value":value,"status":status,"source":"observation","provenance":["observation"],"confidence":.9}}}


def test_daylight_state_known_sufficient():
    out=PreRealizationDaylightDeficitV1().evaluate(map_with([daylight_resource("a",30,1)]),demand())
    assert out["floors"][0]["evidence_state"]=="KNOWN_SUFFICIENT" and not out["additional_daylight_source_eligible"]


def test_daylight_state_known_deficit_is_the_only_eligible_state():
    out=PreRealizationDaylightDeficitV1().evaluate(map_with([daylight_resource("a",3,1)]),demand())
    assert out["floors"][0]["evidence_state"]=="KNOWN_DEFICIT" and out["additional_daylight_source_eligible"]


def test_daylight_state_unknown_supply_never_triggers_source():
    out=PreRealizationDaylightDeficitV1().evaluate({"resources":[]},demand())
    assert out["floors"][0]["evidence_state"]=="UNKNOWN_SUPPLY" and not out["additional_daylight_source_eligible"]
    assert out["new_source_requirements"] is None and out["demonstrated_deficits"]==[]


def test_daylight_state_incomplete_evidence_never_triggers_source():
    resources=[daylight_resource("known",30,1),daylight_resource("unknown",4,None,"unknown")]
    out=PreRealizationDaylightDeficitV1().evaluate(map_with(resources),demand())
    assert out["floors"][0]["evidence_state"]=="INCOMPLETE_EVIDENCE" and not out["additional_daylight_source_eligible"]


def test_source_contains_no_directional_or_fixed_band_shortcut():
    import core.architecture.reasoning.evidence_based_site_resource_region_derivation_v1 as module
    source=inspect.getsource(module).lower(); compass=["".join(x) for x in (("n","o","r","t","h"),("e","a","s","t"),("s","o","u","t","h"),("w","e","s","t"))]
    assert not any(('"'+x+'"') in source or ("'"+x+"'") in source for x in compass)
    assert "parcel"+"2" not in source and "parcel"+" 2" not in source
