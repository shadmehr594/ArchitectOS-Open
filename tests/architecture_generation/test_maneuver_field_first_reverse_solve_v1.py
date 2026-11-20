import json
from pathlib import Path
from shapely.geometry import box

from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.maneuver_field_first_reverse_solve_v1 import ManeuverFieldFirstReverseSolveV1

ROOT=Path(__file__).resolve().parents[2]


def real_result():
    source=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1]
    data=json.loads(source.read_text(encoding='utf-8'));helper=BasementRampParkingDesignReasonerV2()
    frame=helper._frame(data['site']['parcel'],data['site']['frontage'])
    inner=helper._to_local_polygon(data['physical_basement_wall']['inner_face'],frame)
    return ManeuverFieldFirstReverseSolveV1().resolve(inner)


def test_search_is_field_first_and_does_not_reuse_terminal_candidates():
    r=real_result();assert r['maneuver_field_first'] is True
    assert r['old_terminal_postprocessing_reused'] is False
    assert r['v3_terminal_geometry_frozen_as_input'] is False


def test_every_field_edge_has_both_approach_senses():
    r=real_result();keys={}
    for t in r['field_edge_trials']: keys.setdefault((t['field_id'],t['edge']),set()).add(t['approach_sense'])
    assert keys and all(v=={'into_field','away_from_field'} for v in keys.values())


def test_large_synthetic_envelope_proves_reverse_constructor():
    r=ManeuverFieldFirstReverseSolveV1().resolve(box(0,0,20,30));valid=[c for c in r['candidates'] if c['geometry_status']=='ramp_operational']
    assert valid
    c=valid[0];assert c['end_interface_width']>=3
    assert c['ramp_maneuver_overlap_area']<=1e-7
    assert c['terminal_leg_length']>0 and c['topology']['R_inner']>=5
    assert c['start_on_legal_frontage']
    assert c['end_left_z']==c['end_center_z']==c['end_right_z']==-2.4


def test_real_result_reports_first_geometric_contradiction_without_false_infeasibility_source():
    r=real_result();e=r['first_geometric_contradiction']
    assert e['required_outer_radius']==8.5
    assert e['available_transverse_clear_width']<10
    assert 'no_positive_terminal_leg_from_any_contained_field_edge' in e['failure_reasons']


def test_deterministic_repeat():
    a=real_result();b=real_result();assert a['hard_valid_candidates']==b['hard_valid_candidates']
    assert a['first_geometric_contradiction']==b['first_geometric_contradiction']
