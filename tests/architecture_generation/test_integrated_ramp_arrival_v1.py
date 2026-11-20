import json
from pathlib import Path
from shapely.geometry import box
from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.integrated_ramp_arrival_v1 import IntegratedRampArrivalV1
ROOT=Path(__file__).resolve().parents[2]

def real_result():
    p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];d=json.loads(p.read_text())
    h=BasementRampParkingDesignReasonerV2();f=h._frame(d['site']['parcel'],d['site']['frontage']);inner=h._to_local_polygon(d['physical_basement_wall']['inner_face'],f)
    return IntegratedRampArrivalV1().resolve(inner)

def test_family_is_independent_and_has_no_terminal_leg_requirement():
    r=real_result();assert r['integrated_arrival_topology'] is True
    assert r['separate_terminal_leg_required'] is False and r['old_reverse_solve_reused'] is False

def test_all_field_edges_and_both_approach_senses_are_tested():
    r=real_result();groups={}
    for t in r['arrival_edge_trials']:groups.setdefault((t['field_id'],t['edge']),set()).add(t['approach_sense'])
    assert groups and all(v=={'into_field','away_from_field'} for v in groups.values())

def test_large_envelope_proves_integrated_arrival_constructor():
    r=IntegratedRampArrivalV1().resolve(box(0,0,20,30));valid=[c for c in r['candidates'] if c['geometry_status']=='ramp_operational'];assert valid
    c=valid[0];assert c['topology']['leg_2_length']==0
    assert c['arrival_interface_width']>=3 and c['ramp_maneuver_overlap_area']<=1e-7
    assert c['end_left_z']==c['end_center_z']==c['end_right_z']==-2.4
    assert c['topology']['R_inner']>=5

def test_real_failure_is_not_inherited_from_reverse_solver():
    r=real_result();assert r['old_reverse_solve_reused'] is False
    assert r['first_geometric_contradiction']['minimum_arrival_transverse_mismatch']>0

def test_d_unchanged_deterministic_result():
    a=real_result();b=real_result();assert a['hard_valid_candidates']==b['hard_valid_candidates']
    assert a['first_geometric_contradiction']==b['first_geometric_contradiction']
