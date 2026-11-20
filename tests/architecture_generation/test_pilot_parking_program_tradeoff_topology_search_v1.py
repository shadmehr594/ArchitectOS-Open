import hashlib, json
from pathlib import Path

from shapely.geometry import Polygon

from core.architecture.reasoning.pilot_parking_program_tradeoff_topology_search_v1 import (
    PilotParkingProgramTradeoffTopologySearchV1,
)

ROOT = Path(__file__).resolve().parents[2]


def inputs():
    p = sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1]
    r = sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json'))[-1]
    return json.loads(p.read_text()), json.loads(r.read_text())['baseline_scenario_a']


def result(preferences=None):
    b, a = inputs()
    return PilotParkingProgramTradeoffTopologySearchV1().resolve(b['site'], b['requirements'], a, preferences)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def test_real_parcel_k_families_capacities_and_five_meter_search_are_used():
    r = result()
    assert r['source_parcel'][0] == [9.495348, 22.127313]
    assert r['source_road_width'] == 10.0
    assert r['topology_families_explored'] == [f'PILOT-K{i:02d}' for i in range(1, 8)]
    assert {c['parking_count'] for c in r['candidates']} == {2, 3, 4}
    assert 5.0 in r['maneuvering_search_targets']['values']
    assert r['maneuvering_search_targets']['classification'] == 'engineering_maneuvering_search_target'


def test_every_review_stall_has_internal_path_to_core():
    for candidate in result()['human_review_candidates']:
        access = candidate['post_parking_pedestrian_access']
        assert access['all_parking_users_reach_core_internally']
        assert len(access['stall_results']) == candidate['parking_count']
        assert all(s['parking_to_core_access_status'] != 'not_feasible' for s in access['stall_results'])
        assert all(s['parking_to_lobby_path'] for s in access['stall_results'])


def test_crossing_and_conflict_remain_explicit_and_independent_use_unproven():
    for candidate in result()['human_review_candidates']:
        access = candidate['post_parking_pedestrian_access']
        assert access['parking_to_core_crossing_count'] >= 0
        assert access['parking_to_core_vehicle_conflict_status'] in {'clear', 'controlled_crossings_require_validation'}
        assert candidate['independently_usable_parking_count'] == 0
        assert candidate['vehicle_maneuvering_status'] == 'pending_vehicle_model_validation'


def test_storage_polygons_respect_user_design_area_limit_and_wc_is_pending():
    r = result()
    k4 = next(c for c in r['human_review_candidates'] if c['family'] == 'PILOT-K04')
    for allocation in k4['residual_space_program']['allocations']:
        if allocation['program'] == 'residential_storage':
            assert 0 < Polygon(allocation['polygon']).area <= 6.0
    k5 = next(c for c in r['human_review_candidates'] if c['family'] == 'PILOT-K05')
    residual = k5['residual_space_program']
    if residual['common_wc_generated']:
        assert residual['common_wc_regulatory_status'] == 'pending_rule_resolution'


def test_entrance_modes_are_user_controllable():
    r = result({'allow_combined_vehicle_pedestrian_gate': False})
    assert 'combined_vehicle_pedestrian_gate_with_wicket' not in r['entrance_modes_explored']
    assert all(c['entrance_mode'] != 'combined_vehicle_pedestrian_gate_with_wicket' for c in r['candidates'])
    assert 'shared_vehicle_pedestrian_access' not in r['entrance_modes_explored']


def test_required_whole_plan_metrics_exist():
    keys = {'parking_count', 'parking_count_pending_vehicle_model_validation', 'maneuvering_field_area',
            'maneuvering_field_dimensions', 'frontage_vehicle_width', 'frontage_pedestrian_width',
            'commercial_frontage', 'parking_to_core_path_length', 'parking_to_core_crossing_count',
            'street_to_core_path_length', 'commercial_area', 'largest_commercial_rectangle',
            'residential_storage_count', 'residential_storage_total_area', 'common_wc_generated',
            'unallocated_residual_area', 'vehicle_circulation_area', 'pedestrian_circulation_area',
            'common_circulation_area', 'service_area', 'net_programmed_area',
            'whole_plan_space_utilization_ratio'}
    assert all(keys <= set(c['metrics']) for c in result()['human_review_candidates'])


def test_baseline_and_program_state_are_preserved_without_final_selection():
    b, a = inputs()
    before = digest((b, a))
    r = PilotParkingProgramTradeoffTopologySearchV1().resolve(b['site'], b['requirements'], a)
    assert before == digest((b, a))
    assert r['baseline_geometry_preserved'] and not r['final_selection_performed']
    assert r['final_scenario_b_candidate'] is None
    assert not r['program_changed'] and not r['basement_deleted'] and not r['basement_removal_approved']
    assert not r['structure_executed'] and not r['bim_executed'] and not r['ifc_executed']
