import json
from pathlib import Path
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.vertical_circulation_core_level_aware_v2 import VerticalCirculationCoreLevelAwareV2
ROOT=Path(__file__).resolve().parents[2]

def result():
 p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];d=json.loads(p.read_text());h=BasementRampParkingDesignReasonerV2();f=h._frame(d['site']['parcel'],d['site']['frontage']);inner=h._to_local_polygon(d['physical_basement_wall']['inner_face'],f);gf=json.loads(sorted(p.parent.glob('ground_floor_frontage_access_v1_*/PARCEL2_GROUND_FLOOR_FRONTAGE_ACCESS_V1.json'))[-1].read_text());rp=json.loads(sorted(p.parent.glob('regulation_aware_straight_parking_*/PARCEL2_REGULATION_AWARE_STRAIGHT_RAMP_PARKING.json'))[-1].read_text());vc=json.loads(sorted(p.parent.glob('vertical_core_placement_v1_*/PARCEL2_VERTICAL_CIRCULATION_CORE_PLACEMENT_V1.json'))[-1].read_text());return rp,VerticalCirculationCoreLevelAwareV2().resolve(inner,gf['selected_diagnostic_candidate'],rp['selected_candidate'],vc['best_whole_building_candidate'])

def test_explicit_levels_and_spans():
 _,r=result();assert r['level_contract']=={'basement_elevation':-2.4,'ground_elevation':0.0,'first_floor_elevation':4.7,'second_floor_elevation':7.94};assert [r['floor_to_floor_spans'][k]['rise'] for k in ('B1_GF','GF_F1','F1_F2')]==[2.4,4.7,3.24]

def test_counts_derived_per_span_and_policy_limits():
 _,r=result();s=r['selected_candidate']['stairs_by_span'];assert [s[k]['riser_count'] for k in s]==[14,27,18]
 assert len({s[k]['riser_count'] for k in s})==3
 for x in s.values():assert x['actual_riser_height']<=.18+1e-9 and x['tread_depth']>=.28 and x['clear_width']==1.2

def test_stair_xyz_landings_and_real_treads():
 _,r=result()
 for s in r['selected_candidate']['stairs_by_span'].values():
  assert s['bottom_interface'][2]==s['start_z'] and abs(s['top_interface'][2]-s['end_z'])<1e-9 and s['landings'] and s['landings'][0]['z']>s['start_z']
  assert all(f['tread_lines'] and f['start_point_xyz'] and f['end_point_xyz'] and f['direction_up'] for f in s['flights'])

def test_old_core_is_honestly_resized_and_locally_revalidated():
 _,r=result();assert r['local_re_evaluation_only'] and r['previous_candidate_remained_valid'] is False;assert r['selected_candidate']['core_dimensions'][1]>r['previous_core_dimensions'][1]

def test_elevator_all_levels_resolved():
 _,r=result();e=r['selected_candidate']['elevator'];assert set(e['door_interfaces_by_level'])=={'B1','GF','F1','F2'} and e['vertical_extent']==[-2.4,7.94] and e['upper_floor_vertical_span_status']=='resolved_from_explicit_level_contract'

def test_context_contract_includes_frontage_ramp_corridor_and_two_stalls():
 rp,r=result();c=r['selected_candidate'];assert c['ground_floor']['commercial_space_polygons'] and c['ground_floor']['pedestrian_corridor'] and c['ground_floor']['vehicle_entrance_width']==3
 assert c['basement']['parking_capacity_preserved']==rp['selected_candidate']['parking_stall_count']==2

def test_upper_arrivals_have_common_distribution_interfaces():
 _,r=result();u=r['selected_candidate']['upper_floor'];assert u['common_distribution'] and u['unit_a_entry_interface'] and u['unit_b_entry_interface']

def test_renderer_authority_and_no_pending_floor_elevation():
 _,r=result();c=r['selected_candidate'];assert c['renderer_authority']=='production_contract_only';assert 'pending_program_floor_elevation' not in json.dumps(r)

def test_repeat_is_deterministic():assert result()[1]==result()[1]
