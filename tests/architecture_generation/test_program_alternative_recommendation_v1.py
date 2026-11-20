import json
from pathlib import Path
from core.architecture.reasoning.program_alternative_recommendation_v1 import ProgramAlternativeRecommendationV1
ROOT=Path(__file__).resolve().parents[2]
def source():
 p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/commercial_spatial_quality_tradeoff_v1_*/PARCEL2_COMMERCIAL_SPATIAL_QUALITY_TRADEOFF_V1.json'))[-1];return json.loads(p.read_text())
def result():return ProgramAlternativeRecommendationV1().resolve(source())
def test_seven_of_seven_triggers_program_escalation():
 r=result();assert r['local_candidate_count']==7 and r['local_commercial_quality_failure_count']==7;assert r['local_core_optimization_exhausted'] and r['local_optimization_status']=='exhausted';assert r['recommendation_strength']=='strong'
def test_recommendation_names_pilot_and_basement_removal_evaluation():
 r=result();assert r['recommended_next_scenario']=='pilot_parking_without_basement';assert r['recommended_next_action']=='generate_pilot_parking_feasibility_study';assert r['basement_removal_recommended_for_evaluation'] and not r['basement_removal_approved']
def test_escalation_does_not_mutate_program_or_baseline():
 r=result();assert not r['program_changed'] and not r['basement_deleted'];assert not r['baseline_geometry_regenerated'];assert r['baseline_scenario_a']['geometry_preserved_as_read_only_baseline'];assert r['baseline_scenario_a']['geometry_status']=='hard_valid'
def test_pilot_is_not_claimed_feasible_and_capacity_not_invented():
 r=result();assert r['pilot_parking_feasibility_status']=='not_tested';assert r['pilot_parking_capacity'] is None;assert not r['pilot_parking_claimed_feasible'];assert not r['pilot_geometry_generated']
def test_future_pilot_study_allows_core_repositioning_but_is_not_run():
 p=result()['pilot_study_contract'];assert p['core_repositioning_permitted'];assert not p['existing_core_reuse_required'];assert p['status']=='not_generated' and not p['geometry_generation_executed']
def test_no_protected_downstream_execution():
 r=result();assert not r['structure_executed'] and not r['bim_executed'] and not r['ifc_executed'];assert r['human_decision_required']
def test_baseline_fingerprint_is_deterministic():assert result()['baseline_scenario_a']['geometry_preservation_fingerprint']==result()['baseline_scenario_a']['geometry_preservation_fingerprint']
