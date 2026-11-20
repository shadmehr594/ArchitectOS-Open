import json
from pathlib import Path
from shapely.geometry import Polygon
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.ground_floor_frontage_program_v1 import GroundFloorFrontageProgramV1

ROOT=Path(__file__).resolve().parents[2]

def result():
 p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];d=json.loads(p.read_text());h=BasementRampParkingDesignReasonerV2();f=h._frame(d['site']['parcel'],d['site']['frontage']);inner=h._to_local_polygon(d['physical_basement_wall']['inner_face'],f)
 ramp=sorted(p.parent.glob('regulation_aware_straight_parking_*/PARCEL2_REGULATION_AWARE_STRAIGHT_RAMP_PARKING.json'))[-1];rd=json.loads(ramp.read_text());reservations=[c for c in rd['straight_candidates'] if c['slope']==.16 and c['status']=='architecture_selected_candidate']
 return inner,GroundFloorFrontageProgramV1().resolve(inner,reservations,d['requirements']['parking_pedestrian']['required_clear_width'])

def test_frontage_allocations_and_three_functions_are_real_intervals():
 inner,r=result();u0,_,u1,_=inner.bounds
 for c in r['candidates']:
  assert c['geometry_status']=='hard_valid' and c['publication_status']=='pending_rule_resolution'
  assert all(u0<=a<b<=u1 for a,b in [c['vehicle_access_interval'],c['pedestrian_access_interval'],c['commercial_access_interval']])
  assert c['mixed_use_access_graph']['STREET'].keys()=={'VEHICLE_ACCESS','COMMON_PEDESTRIAN_ACCESS','COMMERCIAL_ACCESS'}

def test_pedestrian_spine_is_independent_clear_and_connected():
 _,r=result()
 for c in r['candidates']:
  assert c['ramp_overlap_area']==0 and c['commercial_overlap_area']==0 and c['pedestrian_vehicle_conflict'] is False
  assert c['discharge_route_status']=='resolved' and c['future_core_interface_width']>0 and c['pedestrian_clear_width']>=r['active_pedestrian_clear_width']-1e-7

def test_point_contact_is_rejected_as_interface():
 assert GroundFloorFrontageProgramV1.interface_is_linear([[0,0],[0,0]]) is False
 assert GroundFloorFrontageProgramV1.interface_is_linear([[0,0],[1,0]]) is True

def test_commercial_frontage_is_continuous_and_usable():
 _,r=result()
 assert all(c['commercial_frontage_width']>0 and c['commercial_frontage_continuity']=='continuous' and c['largest_contiguous_commercial_field']>0 for c in r['candidates'])

def test_mirror_families_are_generated_without_parcel_coordinates_in_reasoner():
 _,r=result();assert {c['arrangement_family'] for c in r['candidates']}=={'COMMERCIAL | PEDESTRIAN | VEHICLE','VEHICLE | PEDESTRIAN | COMMERCIAL'}
 source=(ROOT/'core/architecture/reasoning/ground_floor_frontage_program_v1.py').read_text();assert '9.4' not in source and 'Parcel 2' not in source

def test_corridor_stops_at_core_and_releases_old_full_depth_area():
 _,r=result()
 assert all(c['corridor_end'][1]==c['core_interface'][0][1] and c['corridor_length']<19.5 and c['released_old_corridor_area']>0 for c in r['candidates'])

def test_egress_concepts_are_distinct_and_unresolved_without_authority():
 _,r=result();e=r['candidates'][0]['fire_egress_evaluation']
 assert e['rule_status']=='pending_rule_resolution'
 assert set(e['evaluations'])=={'total_exit_access_travel_distance','common_path_of_egress_travel','dead_end_corridor_length'}
 assert r['ground_floor_frontage_status']=='unresolved' and r['selected_candidate'] is None and r['selected_diagnostic_candidate']

def test_future_core_is_reservation_only_and_downstream_paths_are_not_invoked():
 _,r=result()
 assert r['stair_geometry_generated'] is False and r['elevator_geometry_generated'] is False and r['core_geometry_generated'] is False
 assert all(c['future_core_geometry_generated'] is False and c['vertical_circulation_core']['geometry_status']=='not_generated' for c in r['candidates'])

def test_repeat_is_deterministic():
 assert result()[1]==result()[1]
