import json
from pathlib import Path
from shapely.geometry import Polygon

from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.ramp_architecture_selection_v1 import RampArchitectureSelectionV1
from core.architecture.reasoning.ramp_slope_policy_v1 import RampSlopePolicyV1
from core.architecture.reasoning.straight_ramp_parking_branch_v1 import StraightRampParkingBranchV1

ROOT=Path(__file__).resolve().parents[2]

def fixture():
    p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1]
    d=json.loads(p.read_text());h=BasementRampParkingDesignReasonerV2();f=h._frame(d['site']['parcel'],d['site']['frontage'])
    inner=h._to_local_polygon(d['physical_basement_wall']['inner_face'],f)
    r=StraightRampParkingBranchV1().resolve(inner,2,{'parking_use':'small_private_covered_parking','project_allows_17_percent':True})
    return inner,r

def test_parking_class_and_policy_are_context_resolved():
    p=RampSlopePolicyV1();closed=p.resolve('small',{});active=p.resolve('small',{'parking_use':'small_private_covered_parking','project_allows_17_percent':True})
    assert closed['slope_candidates']==[.15] and closed['global_17_percent_enable'] is False
    assert active['parking_class']=='small' and active['slope_candidates']==[.15,.16,.17]

def test_17_transition_segments_and_vertical_drop_conservation():
    _,r=fixture();c=next(c for c in r['candidates'] if c['slope']==.17)
    assert [s['length'] for s in c['segments']]==[1.,13.117647058823529,1.]
    assert [s['grade'] for s in c['segments']]==[.085,.17,.085]
    assert abs(c['achieved_vertical_drop']-2.4)<1e-9

def test_three_physical_paths_and_geometry_contract():
    inner,r=fixture()
    for c in r['candidates']:
        assert c['L_left']==c['L_center']==c['L_right']==c['horizontal_run']
        assert inner.buffer(1e-5).covers(Polygon(c['ramp_surface']))

def test_frozen_straight15_rejection_is_not_reopened():
    _,r=fixture();assert all('maneuver_failed_frozen_straight15_connection_proof' in c['failure_reasons'] for c in r['candidates'] if c['slope']==.15)

def test_maneuver_parking_and_return_are_complete_for_16_and_17():
    _,r=fixture()
    for c in [x for x in r['candidates'] if x['slope'] in (.16,.17)]:
        assert c['ramp_maneuver_overlap_area']==0 and c['arrival_interface_width']>=3
        assert c['parking_stall_count']==c['required_stall_count']==2
        assert c['vehicle_return_status']=='resolved'
        assert all(p['other_stalls_occupied'] and p['independent_entry'] and p['independent_exit'] and p['return_to_ramp'] for p in c['vehicle_paths'])

def test_architecture_ranking_and_two_curve_status_semantics():
    _,r=fixture();ranker=RampArchitectureSelectionV1();selected=ranker.select(r['candidates'])
    assert selected['slope']==.16
    synthetic=[dict(selected,slope=.15,parking_stall_count=2,largest_contiguous_usable_field=62),dict(selected,slope=.17,parking_stall_count=3,largest_contiguous_usable_field=100)]
    assert ranker.select(synthetic)['slope']==.17
    frozen=ranker.freeze_two_curve_baseline('TC-M4.5-X0-Y1-east-left_right-A30-B30-T6.647',61.722)
    assert frozen['geometry_status']=='hard_valid' and frozen['architecture_selection_status']=='valid_but_not_preferred_for_parcel2'

def test_repeat_is_deterministic():
    _,a=fixture();_,b=fixture();assert a==b
