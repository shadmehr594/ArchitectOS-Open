from copy import deepcopy
import json, sys
from pathlib import Path

ROOT=Path(r"<repo-root>")
sys.path.insert(0,str(ROOT/"core/architecture/reasoning"))
from parcel2_architectural_graph_floor_plan_synthesizer_v8 import ArchitecturalGraphFloorPlanSynthesizerV8, verify_projection_policy

SRC=ROOT/"exports/DEFAULT/parcel2_residential_room_planning_daylight_v4_20260913_131505/PARCEL2_RESIDENTIAL_ROOM_PLANNING_DAYLIGHT_V4.json"
EV=ROOT/"core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json"
POL=ROOT/"core/architecture/contracts/jurisdictional_projection_policy_v1.json"
PAT=ROOT/"core/architecture/knowledge/residential_floor_precedent_patterns_v2.json"
PROFILE="PARCEL2_MINAB_WORKING_20260913"

def load(path): return json.loads(path.read_text(encoding="utf-8"))
def engine(policy=None): return ArchitecturalGraphFloorPlanSynthesizerV8(load(EV),load(PAT),policy or load(POL),PROFILE)
def first_group(): return engine().group(load(SRC))[0][1]

def test_policy_is_generic_quarantined_and_exactly_evidence_linked():
    policy=load(POL); profile=policy["profiles"][0]
    assert policy["generic_defaults"]["status"]=="PROHIBITED"
    assert profile["status"]=="OPTIONAL_ALLOWED" and profile["authority_class"]=="PROJECT_LOCAL_CONFIRMED_CONDITION"
    assert not profile["applicability"]["use_for_regulatory_acceptance"] and profile["applicability"]["evidence_pending"]
    assert all(r["min_clear_height_m"] is None for r in profile["rules"])
    values={r["rule_id"]:r["max_projection_depth_m"] for r in profile["rules"]}
    assert values["MINAB_1_6_8_STREET_10_TO_20"]==.8 and values["MINAB_1_6_8_STREET_OVER_20"]==1.2
    assert verify_projection_policy(policy,PROFILE)["status"]=="PASS"

def test_determinism_no_source_mutation_and_all_optional_moves():
    group=first_group(); frozen=deepcopy(group); a=engine().synthesize_group(group); b=engine().synthesize_group(group)
    assert a==b and group==frozen and len(a)==10
    assert {p["projection_balcony_opportunity"]["candidate_type"] for p in a}=={"NO_PROJECTION","PARTIAL_PROJECTION","FULL_ALLOWED_PROJECTION","BALCONY_ONLY","ROOM_EXTENSION_PLUS_BALCONY"}
    assert any(p["projection_balcony_opportunity"]["selected_depth_m"]==.4 for p in a)
    assert any(p["projection_balcony_opportunity"]["selected_depth_m"]==.8 for p in a)

def test_prohibited_profile_generates_no_projection_candidate():
    policy=load(POL); policy["profiles"][0]["status"]="PROHIBITED"
    plans=engine(policy).synthesize_group(engine(policy).group(load(SRC))[0][1])
    assert len(plans)==2
    assert all(p["projection_balcony_opportunity"]["candidate_type"]=="NO_PROJECTION" for p in plans)
    assert all(p["projection_balcony_opportunity"]["polygon"] is None for p in plans)

def test_v8_pipeline_facade_access_rf2_and_truthful_fail_closed():
    for _,group in engine().group(load(SRC)):
        for plan in engine().synthesize_group(group):
            pipe=plan["pipeline"]
            assert pipe.index("FACADE_VALUE_MAP")<pipe.index("DAYLIGHT_SOURCE_BUDGET")<pipe.index("ROOM_PACKING")
            assert plan["facade_value_map"]["created_before_rooms"] and not any(e["cardinal_direction_used"] for e in plan["facade_value_map"]["edges"])
            assert plan["core_common_access"]["shared_access_complete"]
            if plan["identity"]["floor_id"]=="RESIDENTIAL_FLOOR_2": assert plan["whole_floor_model"]["rf2_single_sheet"] and len(plan["units"])==2
            assert not plan["REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN"] and not plan["resolved_floor_hypothesis"]
            assert "V8_ADJACENCY_FIRST_ROOM_PACKING_NOT_YET_GEOMETRICALLY_RESOLVED" in plan["blockers"]
            assert plan["authority_separation"]["projection_regulatory_acceptance"] is False
