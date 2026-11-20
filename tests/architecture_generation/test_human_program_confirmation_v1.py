import json
from pathlib import Path
import pytest
from core.architecture.reasoning.human_program_confirmation_v1 import (
    HumanProgramConfirmationV1, ProgramConfirmationSemanticConsistencyAudit)

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = json.loads((ROOT / "core/architecture/contracts/parcel2_human_program_evidence_v1.json").read_text(encoding="utf-8"))

def base():
    ids = ["commercial","residential_floors","residential_units_per_floor","terrace_per_unit","parking","stair","elevator","lobby_common_circulation","dedicated_pedestrian_entrance","residential_daylight"]
    items = [{"id": x, "function": x, "count": None, "evidence_status": "unresolved_authoritative_program_input"} for x in ids]
    for index in (4,5,6,7):
        items[index].update(count=(2 if index==4 else 1), requirement_type="hard",
                            evidence_status="authoritative_resolved")
    return {"contract":"BASE","project_id":"parcel_2","program_items":items}

def build(evidence=None, deficit="UNKNOWN"):
    return HumanProgramConfirmationV1().build(authoritative_contract=base(), evidence_contract=evidence or EVIDENCE, daylight_deficit_state=deficit)

def item(result, item_id): return next(x for x in result["program_items"] if x["id"] == item_id)

def test_explicit_requirement_resolves_with_trace():
    x=item(build(),"commercial")
    assert x["status"]=="explicit_user_requirement_resolved" and x["evidence_role"]=="requirement" and x["requirement_type"]=="hard"
    assert x["source_contract"] and x["source_path"] and x["key"] and x["provenance"] and x["confidence"]==1.0

def test_per_record_source_path_preserves_new_confirmation_provenance():
    x=item(build(),"parking_ownership")
    assert "continuation-request-2026-09-12" in x["source_path"]
    assert "continuation-request-2026-09-12" in x["provenance"][0]["source_path"]

def test_design_intent_is_not_hard_regulation():
    assert item(build(),"residential_daylight")["requirement_type"]=="preferred"
    bad=json.loads(json.dumps(EVIDENCE)); next(r for r in bad["evidence_records"] if r["id"]=="residential_daylight")["requirement_type"]="hard"
    with pytest.raises(ValueError,match="hard regulation"): build(bad)

def test_topology_discussion_is_non_binding():
    x=item(build(),"orientation_topology")
    assert x["binding"] is False and x["hardcoded_topology"] is None and x["requirement_type"]=="optional"

def test_lightwell_only_after_known_deficit():
    assert build(deficit="UNKNOWN")["lightwell_eligibility"]["eligible"] is False
    assert build(deficit="NO_DEFICIT")["lightwell_eligibility"]["eligible"] is False
    assert build(deficit="KNOWN_DEFICIT")["lightwell_eligibility"]["eligible"] is True

def test_unresolved_counts_get_no_defaults_and_block_solve():
    unresolved=json.loads(json.dumps(EVIDENCE))
    unresolved["evidence_records"]=[r for r in unresolved["evidence_records"] if r["id"] not in {"residential_floors","residential_units_per_floor"}]
    result=build(unresolved); assert result["required_human_decisions_for_clean_solve"]==["residential_floors","residential_units_per_floor"]
    assert result["clean_parcel_2_resolve_ready"] is False and result["defaults_applied"] is False
    for key in result["required_human_decisions_for_clean_solve"]:
        assert item(result,key)["count"] is None and item(result,key)["downstream_demand_state"]=="unknown"

def test_historical_geometry_candidate_data_rejected():
    bad=json.loads(json.dumps(EVIDENCE)); bad["evidence_records"][0]["source_kind"]="historical_candidate"
    with pytest.raises(ValueError,match="historical geometry/candidate"): build(bad)
    bad=json.loads(json.dumps(EVIDENCE)); bad["evidence_records"][0]["geometry"]={"coordinates":[[0,0]]}
    with pytest.raises(ValueError,match="forbidden"): build(bad)

def test_pre_solve_state_and_terrace_cardinality():
    result=build(); terrace=item(result,"terrace_per_unit")
    assert terrace["count"] is None and terrace["cardinality_status"]=="unresolved"
    assert result["parcel_2_resolve_executed"] is False and result["winner"] is None
    assert result["final_selection_performed"] is False and result["room_layout_generated"] is False and result["final_windows_generated"] is False
    assert all(result[k] is False for k in ("structure_executed","bim_executed","ifc_executed","render_executed"))

def test_confirmed_floor_schedule_is_machine_consumable_and_ready():
    result=build(); floors=item(result,"residential_floors"); units=item(result,"residential_units_per_floor")
    assert floors["count"]==2 and floors["status"]=="explicit_user_requirement_resolved"
    assert units["value"]=={"residential_floor_1":1,"residential_floor_2":2}
    assert units["total_units"]==3 and units["schedule_cardinality"]=="explicit_by_floor"
    assert result["required_human_decisions_for_clean_solve"]==[]
    assert result["clean_parcel_2_resolve_ready"] is True

def test_semantic_layers_are_consistent_for_every_item():
    result=build(); audit=ProgramConfirmationSemanticConsistencyAudit().audit(result["program_items"])
    assert audit["passed"] is True and audit["violations"]==[]
    assert not [x for x in result["program_items"]
                if x.get("evidence_status")=="authoritative_resolved"
                and x.get("downstream_demand_state")=="unknown"]

def test_base_authority_is_preserved_and_known():
    result=build()
    for item_id in ("parking","stair","elevator","lobby_common_circulation"):
        x=item(result,item_id)
        assert x["evidence_status"]=="authoritative_resolved"
        assert x["status"]=="authoritative_resolved" and x["downstream_demand_state"]=="known"

def test_terrace_and_pedestrian_entrance_semantics_are_not_promoted():
    result=build(); terrace=item(result,"terrace_per_unit"); entrance=item(result,"dedicated_pedestrian_entrance")
    assert terrace["requirement_type"]=="preferred" and terrace["cardinality_status"]=="unresolved"
    assert entrance["requirement_type"]=="optional" and entrance["mandatory"] is False

def test_conflict_is_fail_closed_and_unknown():
    conflicting=json.loads(json.dumps(EVIDENCE))
    record=next(r for r in conflicting["evidence_records"] if r["id"]=="commercial")
    other=json.loads(json.dumps(record)); other["key"]="commercial_conflict"; other["value"]=False
    conflicting["evidence_records"].append(other)
    x=item(build(conflicting),"commercial")
    assert x["evidence_status"]=="conflicted_sources" and x["status"]=="conflicted_sources"
    assert x["downstream_demand_state"]=="unknown"
