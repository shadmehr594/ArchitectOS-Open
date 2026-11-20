import json
from pathlib import Path
from math import hypot
from shapely.geometry import Polygon
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.two_curve_ramp_topology_v1 import TwoCurveRampTopologyV1
ROOT=Path(__file__).resolve().parents[2]

def fixture():
 p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];d=json.loads(p.read_text());h=BasementRampParkingDesignReasonerV2();f=h._frame(d['site']['parcel'],d['site']['frontage']);inner=h._to_local_polygon(d['physical_basement_wall']['inner_face'],f);return inner,TwoCurveRampTopologyV1().resolve(inner)

def result():return fixture()[1]

def test_new_family_does_not_reuse_single_curve_candidates():
 r=result();assert r['new_search_source']=='two_curve_joint_reverse_geometry';assert r['single_curve_candidates_reused'] is False

def test_real_parcel_has_two_curve_operational_candidate():
 r=result();assert r['hard_valid_candidates'];assert all(c.startswith('TC-') for c in r['hard_valid_candidates'])

def test_hard_valid_band_radius_lengths_grades_and_arrival():
 inner,r=fixture();valid=[c for c in r['candidates'] if c['geometry_status']=='ramp_operational']
 for c in valid:
  t=c['topology'];assert t['curve_A']['R_inner']>=5 and t['curve_B']['R_inner']>=5
  assert abs(t['start'][1]-inner.bounds[1])<=1e-7 and t['z_profile'][0]==0
  assert t['chirality'] in ('right_left','left_right')
  assert inner.buffer(1e-7).covers(Polygon(t['surface']))
  assert min(c['L_left'],c['L_center'],c['L_right'])>=16-1e-7
  assert max(c['max_local_grades'].values())<=.15+1e-7
  assert c['arrival_interface_width']>=3-1e-7 and c['ramp_maneuver_overlap_area']<=1e-7
  assert t['arrival_z']==[-2.4,-2.4,-2.4]

def test_all_tangent_events_are_connected_without_kinks():
 c=next(c for c in result()['candidates'] if c['geometry_status']=='ramp_operational');t=c['topology']
 assert t['curve_A']['tangent_in']==t['centerline'][1]
 assert t['curve_A']['tangent_out']==t['transition_start']
 assert t['transition_end']==t['curve_B']['tangent_in']
 assert t['curve_B']['tangent_out'] in t['centerline']
 pts=t['centerline']
 assert all(hypot(b[0]-a[0],b[1]-a[1])>1e-9 for a,b in zip(pts,pts[1:]))

def test_transition_is_tangent_and_solved_not_fixed():
 r=result();lengths={round(c['topology']['transition_length'],6) for c in r['candidates']};assert len(lengths)>3
 assert min(lengths)<.02 and max(lengths)>1

def test_vehicle_path_and_reverse_are_contract_geometry():
 c=next(c for c in result()['candidates'] if c['geometry_status']=='ramp_operational')
 assert c['return_path']==list(reversed(c['vehicle_path']));assert c['clearance_corridor'];assert c['renderer_authority']=='production_contract_only'

def test_parking_and_downstream_remain_out_of_scope():
 r=result();assert r['parking_search_status']=='not_run';assert r['physical_ramp_published'] is False

def test_repeat_is_deterministic():
 a=result();b=result();assert a['hard_valid_candidates']==b['hard_valid_candidates']
