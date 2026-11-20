import hashlib, json
from pathlib import Path
from core.architecture.reasoning.pilot_parking_compact_circulation_topology_search_v1 import PilotParkingCompactCirculationTopologySearchV1

ROOT=Path(__file__).resolve().parents[2]
def inputs():
 p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];r=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json'))[-1]
 return json.loads(p.read_text()),json.loads(r.read_text())['baseline_scenario_a']
def result():
 b,a=inputs();return PilotParkingCompactCirculationTopologySearchV1().resolve(b['site'],b['requirements'],a)
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()

def test_real_parcel_and_all_j_families_are_used():
 r=result();assert r['source_parcel'][0]==[9.495348,22.127313] and r['source_road_width']==10.0;assert r['topology_families_explored']==[f'PILOT-J{i:02d}' for i in range(1,7)];assert r['candidate_count']==72
def test_circulation_terminates_at_functional_destinations():
 for c in result()['human_review_candidates']:
  assert c['vehicle_access_axis'][-1]==c['vehicle_lane_endpoint'];assert c['pedestrian_path'][-1]==c['pedestrian_corridor_endpoint'];assert c['metrics']['vehicle_dead_run_length']==0 and c['metrics']['pedestrian_dead_run_length']==0
def test_required_efficiency_metrics_and_upper_consequence_exist():
 keys={'vehicle_circulation_area','vehicle_circulation_length','pedestrian_circulation_area','pedestrian_circulation_length','total_circulation_area','vehicle_dead_run_length','pedestrian_dead_run_length','circulation_area_ratio','parking_boundary_adjacency_ratio','parking_terminality_score','core_access_path_length','commercial_area','commercial_frontage','commercial_depth','largest_usable_rectangle','service_zone_area','whole_plan_net_usable_efficiency'}
 for c in result()['human_review_candidates']:
  assert keys<=set(c['metrics']);assert set(c['upper_floor_access_consequence'])>={'common_access_path_length','likely_common_area_consumption','core_position_flexibility','two_unit_distribution_potential'}
def test_capacity_is_generated_but_independent_use_remains_pending():
 r=result();assert {c['parking_count'] for c in r['candidates']}=={2,3}
 for c in r['human_review_candidates']:
  assert c['parking_count']==len(c['parking_stalls']);assert c['independently_usable_parking_count']==0;assert c['vehicle_maneuvering_status']=='pending_vehicle_model_validation';assert not c['vehicle_swept_path_generated']
def test_maneuver_target_is_engineering_search_not_regulation():
 r=result();assert r['maneuvering_search_targets']['classification']=='engineering_maneuvering_search_target';assert not r['maneuvering_search_targets']['regulatory_requirement']
def test_state_preserved_and_no_final_selection():
 b,a=inputs();before=(digest(b),digest(a));r=PilotParkingCompactCirculationTopologySearchV1().resolve(b['site'],b['requirements'],a);assert before==(digest(b),digest(a));assert not r['final_selection_performed'] and r['final_scenario_b_candidate'] is None;assert not r['program_changed'] and not r['basement_deleted'] and not r['basement_removal_approved'];assert not r['structure_executed'] and not r['bim_executed'] and not r['ifc_executed']
