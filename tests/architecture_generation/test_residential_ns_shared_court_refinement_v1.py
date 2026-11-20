import hashlib
import json
from functools import lru_cache
from pathlib import Path
from shapely.geometry import box
from core.architecture.reasoning.buildable_space_utilization_intelligence_v1 import BuildableSpaceUtilizationIntelligenceV1
from core.architecture.reasoning.minab_residential_architectural_rules_v1 import MinabResidentialArchitecturalRulesV1
from core.architecture.reasoning.projection_vertical_stack_intelligence_v1 import ProjectionVerticalStackIntelligenceV1
from core.architecture.reasoning.residential_ns_shared_court_refinement_v1 import ResidentialNSSharedCourtRefinementV1
from core.architecture.reasoning.shared_court_terrace_privacy_separation_v1 import SharedCourtTerracePrivacySeparationV1

ROOT = Path(__file__).resolve().parents[2]


def inputs():
    bp = sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1]
    root = bp.parent
    building = json.loads(bp.read_text(encoding='utf-8'))
    baseline = json.loads(sorted(root.glob('program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json'))[-1].read_text(encoding='utf-8'))['baseline_scenario_a']
    pilot = json.loads(sorted(root.glob('program_driven_pilot_space_composition_v1_*/PROGRAM-A_CONTRACT.json'))[-1].read_text(encoding='utf-8'))['human_review_candidates'][0]
    return building, baseline, pilot


@lru_cache(maxsize=1)
def result():
    b,a,p = inputs()
    return ResidentialNSSharedCourtRefinementV1().resolve(b['site'],a,p,{'jurisdiction':'Minab'})


def test_large_unallocated_area_is_measured_classified_and_ranked_down():
    e=[[0,0],[10,0],[10,10],[0,10]]
    sparse=BuildableSpaceUtilizationIntelligenceV1().resolve(e,[{'space_id':'UNIT-SOUTH','classification':'PRIVATE_UNIT','polygon':[[0,0],[4,0],[4,10],[0,10]]}])
    full=BuildableSpaceUtilizationIntelligenceV1().resolve(e,[{'space_id':'UNIT-SOUTH','classification':'PRIVATE_UNIT','polygon':e}])
    assert sparse['unallocated_buildable_area']==60 and sparse['unallocated_buildable_area_ratio']==.6
    assert sparse['unallocated_residual_polygons'][0]['classification']=='UNALLOCATED_RESIDUAL'
    assert sparse['utilization_status']=='architectural_waste_failure' and not full['architectural_quality_penalties']


def test_ns_preference_is_human_input_and_counterexamples_remain():
    r=result(); assert r['preferred_residential_split_direction']=='north_south'
    assert r['preference_source']=='human_architect_review' and not r['preference_is_final_approval']
    assert {'R-EW-COUNTEREXAMPLE','R-HYBRID-COUNTEREXAMPLE'} <= {c['refinement_family'] for c in r['candidates']}


def test_shared_court_serves_both_and_north_terrace_uses_court_edge():
    ns=[c for c in result()['candidates'] if c['refinement_family'].startswith('NS-')]
    assert all(c['shared_daylight_court']['court_serves_both_units'] for c in ns)
    assert any(c['north_unit_terrace_adjacent_to_shared_daylight_court'] for c in ns)
    assert all(c['maintenance_access_source']=='COMMON' for c in ns)
    court_footprints={json.dumps(c['shared_daylight_court']['court_polygon'],sort_keys=True) for c in ns}
    assert len(court_footprints)>=4
    assert all(c['buildable_space_utilization']['usable_residual_area'] < 1.0 for c in ns)
    ns_e=next(c for c in ns if c['refinement_family']=='NS-E')
    assert ns_e['projection_mode']=='projection_candidate_enabled' and 'PROJECTION_CANDIDATE_ENABLED' in ns_e['candidate_id']


def test_privacy_separator_only_when_needed_has_thickness_and_rechecks_court():
    rules=MinabResidentialArchitecturalRulesV1().resolve()
    maintenance={'maintenance_source':'COMMON','private_unit_crossing':False}
    shared=SharedCourtTerracePrivacySeparationV1().resolve([[3,3],[6.2,3],[6.2,7.2],[3,7.2]],
        [[[0,0],[10,0],[10,3],[0,3]],[[0,7.2],[10,7.2],[10,10],[0,10]]],
        [{'terrace_polygon':[[3,7.2],[6.2,7.2],[6.2,8.2],[3,8.2]]}],maintenance,rules,wall_thickness=.12,wall_end_level=9)
    single=SharedCourtTerracePrivacySeparationV1().resolve([[3,3],[6,3],[6,7],[3,7]],
        [[[0,0],[10,0],[10,3],[0,3]],[[7,7],[10,7],[10,10],[7,10]]],[],maintenance,rules)
    assert shared['privacy_divider_required'] and shared['privacy_wall_thickness']>.0
    assert shared['privacy_wall_thickness_source']=='engineering_assumption' and shared['regulatory_status']=='pending_rule_resolution'
    assert shared['clear_daylight_court_area']<13.44 and shared['clear_daylight_court_min_width']>=3
    assert not single['privacy_divider_required'] and not single['privacy_wall_polygon']


def test_divider_cannot_silently_break_minimum_lightwell():
    rules=MinabResidentialArchitecturalRulesV1().resolve(); maintenance={'maintenance_source':'COMMON','private_unit_crossing':False}
    r=SharedCourtTerracePrivacySeparationV1().resolve([[0,0],[3,0],[3,4],[0,4]],
        [[[0,-3],[3,-3],[3,0],[0,0]],[[0,4],[3,4],[3,7],[0,7]]],
        [{'terrace_polygon':[[0,4],[3,4],[3,5],[0,5]]}],maintenance,rules,wall_thickness=.12)
    assert r['divider_topology_status']=='rejected' and 'lightwell_area_failure' in r['failure_reasons']


def test_projection_stack_uses_lower_slab_and_underside_clearance():
    e=ProjectionVerticalStackIntelligenceV1(); levels={'ground_floor_floor_level':0,'ground_floor_ceiling_level':3.6,
      'first_residential_floor_level':3.8,'first_residential_ceiling_level':6.8,'projection_lower_slab_level':3.8,
      'projection_upper_boundary_level':6.8,'underside_projection_elevation':3.6}
    r=e.resolve(levels,3.5,0,True); assert r['projection_lower_slab_equals_first_residential_floor_level']
    assert r['projection_floor_slab']['level']==3.8 and r['projection_upper_cover_or_next_floor_slab']['level']==6.8
    assert r['clearance_check_geometry']=='underside_of_lower_projection_slab' and r['actual_public_road_clear_height']==3.6
    roof_only=e.resolve({'projection_upper_boundary_level':6.8},3.5,0,True)
    assert roof_only['upper_roof_overhang_only'] and not roof_only['usable_projection_area_claim_permitted']


def test_no_rooms_windows_selection_or_protected_state_mutation():
    b,a,p=inputs(); before=hashlib.sha256(json.dumps((b,a,p),sort_keys=True).encode()).hexdigest()
    r=ResidentialNSSharedCourtRefinementV1().resolve(b['site'],a,p,{'jurisdiction':'Minab'})
    after=hashlib.sha256(json.dumps((b,a,p),sort_keys=True).encode()).hexdigest()
    assert before==after and r['baseline_geometry_preserved']
    assert not r['room_layout_generated'] and not r['final_windows_generated'] and not r['final_selection_performed']
    assert r['final_residential_topology'] is None and not r['program_changed'] and not r['basement_deleted'] and not r['basement_removal_approved']
    assert not r['structure_executed'] and not r['bim_executed'] and not r['ifc_executed']
