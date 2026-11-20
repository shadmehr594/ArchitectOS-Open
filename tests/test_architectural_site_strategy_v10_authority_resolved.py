import json
from pathlib import Path

from core.architecture.reasoning.architectural_site_strategy_v10 import ArchitecturalSiteStrategyV10
from tools.run_architectural_site_strategy_v10_authority_resolved import EXCLUDED, _parcel2


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "core" / "architecture" / "contracts" / "parcel2_minab_lightwell_window_authority_profile_v10_1.json"


def load_profile():
    return json.loads(PROFILE.read_text(encoding="utf-8"))


def test_authority_taxonomy_and_local_nonacceptance():
    profile = load_profile()
    assert set(profile["authority_classes"]) == {"NATIONAL_VERIFIED", "LOCAL_VERIFIED", "PROJECT_LOCAL_CONFIRMED_CONDITION", "USER_REPORTED_LOCAL_RULE", "DESIGN_KNOWLEDGE_NON_AUTHORITATIVE"}
    local = next(x for x in profile["source_documents"] if x["document_id"].startswith("MINAB"))
    assert local["regulatory_acceptance_use"] is False
    assert "NOT_PRESENT" in local["promulgation_status"]


def test_national_dimensions_are_exactly_sourced():
    profile = load_profile()
    engine = profile["resolved_engine_profile"]
    assert engine["parameters"]["lightwell_min_width_m"]["value"] == 3.0
    assert engine["parameters"]["lightwell_min_area_m2"]["value"] == 12.0
    assert engine["opposing_window_min_distance_m"] == 3.0


def test_local_sill_is_not_promoted_to_acceptance():
    engine = load_profile()["resolved_engine_profile"]
    assert engine["parameters"]["neighbor_window_min_sill_m"]["value"] is None
    assert "FAIL_CLOSED" in engine["parameters"]["neighbor_window_min_sill_m"]["status"]


def test_v10_rerun_has_hard_feasible_generic_families_without_winner():
    profile = load_profile()
    site, program = _parcel2()
    result = ArchitecturalSiteStrategyV10().analyze(site, program, profile["resolved_engine_profile"])
    feasible = [x for x in result["strategy_candidates"] if x["hard_feasible"]]
    assert feasible
    assert any(x["core_family"] == "INTER_UNIT_CENTRAL_CORE" for x in feasible)
    assert any(x["lightwell_family"] == "SINGLE_SHARED_REAR_LIGHTWELL" for x in feasible)
    assert result["authoritative_winner"] is None


def test_all_core_families_can_be_exercised_by_authority_rerun():
    profile = load_profile()
    site, program = _parcel2()
    engine = ArchitecturalSiteStrategyV10()
    result = engine.analyze(site, program, profile["resolved_engine_profile"])
    families = {x["family"] for x in result["core_candidate_zones"]}
    assert families == {"INTER_UNIT_CENTRAL_CORE", "SIDE_CORE", "REAR_CORE", "FRONT_CORE_ONLY_IF_JUSTIFIED"}


def test_party_wall_windows_remain_fail_closed():
    profile = load_profile()
    site, program = _parcel2()
    result = ArchitecturalSiteStrategyV10().analyze(site, program, profile["resolved_engine_profile"])
    party = [x for x in result["edge_metadata"] if x["neighbor_relation"] == "PARTY_WALL"]
    assert party and all(x["window_restrictions"].startswith("PROHIBITED") for x in party)


def test_forbidden_domains_are_explicitly_excluded():
    assert EXCLUDED == ["H2", "ELEVATOR_TRAFFIC", "STRUCTURE", "BIM", "IFC", "RENDER", "IMAGE_GENERATION"]
