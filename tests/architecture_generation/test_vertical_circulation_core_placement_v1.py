import json
from pathlib import Path
from shapely.geometry import Polygon
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.vertical_circulation_core_placement_v1 import VerticalCirculationCorePlacementV1
ROOT=Path(__file__).resolve().parents[2]

def result():
 p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];d=json.loads(p.read_text());h=BasementRampParkingDesignReasonerV2();f=h._frame(d['site']['parcel'],d['site']['frontage']);inner=h._to_local_polygon(d['physical_basement_wall']['inner_face'],f);gf=json.loads(sorted(p.parent.glob('ground_floor_frontage_access_v1_*/PARCEL2_GROUND_FLOOR_FRONTAGE_ACCESS_V1.json'))[-1].read_text());rp=json.loads(sorted(p.parent.glob('regulation_aware_straight_parking_*/PARCEL2_REGULATION_AWARE_STRAIGHT_RAMP_PARKING.json'))[-1].read_text());return inner,rp['selected_candidate'],VerticalCirculationCorePlacementV1().resolve(inner,gf['selected_diagnostic_candidate'],rp['selected_candidate'],d['requirements']['core'])

def test_core_stair_elevator_and_lobby_have_real_geometry():
 _,_,r=result();c=r['best_whole_building_candidate'];assert Polygon(c['core_polygon']).area>0 and Polygon(c['stair']['polygon']).area>0 and len(c['stair']['flights'])==2 and c['stair']['landings'] and Polygon(c['elevator']['shaft_polygon']).area>0 and c['common_lobby']['area']>0

def test_corridor_terminates_at_actual_core_and_is_not_fixed_depth():
 _,_,r=result();assert len({round(c['ground_floor']['corridor_length'],3) for c in r['candidates']})>20
 for c in r['candidates']:
  assert c['ground_floor']['corridor_terminates_at_core'] and c['ground_floor']['corridor_centerline'][-1][1]==c['core_polygon'][0][1]
  assert abs(c['ground_floor']['corridor_length']-19.5)>1e-6

def test_valid_candidates_preserve_ramp_parking_and_both_paths():
 _,parking,r=result()
 for c in [x for x in r['candidates'] if x['geometry_status']=='hard_valid']:
  assert c['basement']['ramp_conflict']==0 and c['basement']['parking_capacity_preserved']==parking['parking_stall_count']==2
  assert c['basement']['stall_1_to_core_path']['status']=='resolved' and c['basement']['stall_2_to_core_path']['status']=='resolved'

def test_upper_two_unit_topology_has_independent_interfaces():
 _,_,r=result();c=r['best_whole_building_candidate'];u=c['upper_floor'];assert u['unit_a_entry_interface']!=u['unit_b_entry_interface'] and u['private_field_metrics']['unit_a_allocatable_area']>0 and u['private_field_metrics']['unit_b_allocatable_area']>0 and u['complete_apartment_rooms_generated'] is False

def test_ranking_is_not_corridor_length_only():
 _,_,r=result();assert r['best_whole_building_candidate']['candidate_id']!=r['earliest_feasible_candidate']['candidate_id'];assert r['best_whole_building_candidate']['quality_metrics']['upper_two_unit_preservation']>=r['earliest_feasible_candidate']['quality_metrics']['upper_two_unit_preservation']

def test_discharge_protected_zone_connects_and_parameters_survive():
 _,_,r=result();c=r['best_whole_building_candidate'];assert c['ground_floor']['exterior_discharge_route'];assert c['stair']['protected_zone'] and c['stair']['connects'] and c['stair']['parameters']

def test_fire_rules_remain_pending_and_renderer_is_contract_only():
 _,_,r=result();assert r['fire_egress_rule_status']=='pending_rule_resolution';assert all(c['fire_egress']['rule_status']=='pending_rule_resolution' and c['renderer_authority']=='production_contract_only' for c in r['candidates'])

def test_repeat_is_deterministic():
 assert result()[2]==result()[2]
