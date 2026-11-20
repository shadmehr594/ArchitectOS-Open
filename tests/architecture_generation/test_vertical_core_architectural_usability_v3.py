import json
from pathlib import Path
from shapely.geometry import Polygon
from core.architecture.reasoning.vertical_core_architectural_usability_v3 import VerticalCoreArchitecturalUsabilityV3
from tools.generate_parcel2_vertical_core_architectural_usability_v3 import render

ROOT=Path(__file__).resolve().parents[2]

def result():
 p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/vertical_core_level_aware_v2_*/PARCEL2_VERTICAL_CORE_LEVEL_AWARE_V2.json'))[-1];v2=json.loads(p.read_text());c=v2['context_geometry'];return VerticalCoreArchitecturalUsabilityV3().resolve(v2,Polygon(c['clear_face']),Polygon(c['ramp']))

def test_selected_report_is_single_candidate():
 r=result();c=r['selected_candidate'];q=r['selected_report'];assert q['candidate_id']==q['source_candidate_id']==c['candidate_id']==r['report_candidate_id'];assert q['corridor_length']==c['ground_floor']['corridor_length'];assert q['commercial_retained_area']==c['ground_floor']['commercial_retained_area'];assert not r['mixed_candidate_report_data']

def test_stair_elevator_and_corridor_connect_lobby():
 c=result()['selected_candidate'];assert 'stair_not_connected_to_common_lobby' not in c['hard_failures'];assert 'elevator_not_connected_to_common_lobby' not in c['hard_failures'];assert 'ground_corridor_not_connected_to_core' not in c['hard_failures'];assert c['ground_floor']['corridor_length']<19.5

def test_exterior_discharge_and_front_clearance():
 c=result()['selected_candidate'];assert c['ground_floor']['exterior_discharge_route'];assert all(v['front_clear_depth']>0 and v['front_clear_width']>0 and v['front_clear_polygon'] for v in c['elevator_front_clearance_by_level'].values())

def test_basement_paths_and_parking_preserved():
 c=result()['selected_candidate'];assert c['basement']['parking_capacity_preserved']==2
 for k in ('stall_1_to_core_path','stall_2_to_core_path'):assert c['basement'][k]['status']=='resolved' and not c['basement'][k]['ramp_crossing'] and c['basement'][k]['lobby_connection_status']=='connected'

def test_two_units_are_independently_accessible():
 u=result()['selected_candidate']['upper_floor'];assert u['unit_a_area']>0 and u['unit_b_area']>0;assert u['independent_entry_a'] and u['independent_entry_b'];assert not u['cross_unit_passage_required'];assert u['unit_a_entry_interface'] and u['unit_b_entry_interface']

def test_stair_plan_contract_has_architectural_cut_logic():
 plans=result()['selected_candidate']['floor_stair_plan_by_level'];assert set(plans)=={'B1','GF','F1','F2'};assert plans['B1']['up_direction'];assert plans['F2']['down_direction'];assert plans['GF']['visible_below_cut_geometry'] and plans['GF']['visible_above_cut_geometry']

def test_renderer_contract_and_frozen_stairs():
 r=result();c=r['selected_candidate'];assert r['renderer_authority']=='production_contract_only';assert [c['stairs_by_span'][k]['riser_count'] for k in ('B1_GF','GF_F1','F1_F2')]==[14,27,18]

def test_fire_paths_measured_without_invented_limits():
 f=result()['selected_candidate']['fire_egress'];assert f['total_exit_access_travel_distance'];assert all(x['applicable_limit'] is None for x in f['total_exit_access_travel_distance'].values())

def test_renderer_contains_required_contract_labels():
 p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/vertical_core_level_aware_v2_*/PARCEL2_VERTICAL_CORE_LEVEL_AWARE_V2.json'))[-1];v2=json.loads(p.read_text());r=result();r['context_geometry']=v2['context_geometry'];svg=render(r)
 for label in ('START / UP','ARRIVAL / DOWN','GROUND FLOOR / GF','COMMERCIAL','VEHICLE 3.00m','PEDESTRIAN 1.20m','ELEVATOR DOOR','CORRIDOR INTERFACE','PRODUCTION CONTRACT ONLY'):assert label in svg
