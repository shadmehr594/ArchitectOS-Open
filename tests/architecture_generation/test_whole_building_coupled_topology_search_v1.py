import hashlib,json
from functools import lru_cache
from pathlib import Path
from shapely.geometry import Polygon
from core.architecture.reasoning.architectural_frontage_value_intelligence_v1 import ArchitecturalFrontageValueIntelligenceV1
from core.architecture.reasoning.whole_building_coupled_topology_search_v1 import WholeBuildingCoupledTopologySearchV1

ROOT=Path(__file__).resolve().parents[2]
def inputs():
    bp=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];root=bp.parent
    b=json.loads(bp.read_text(encoding='utf-8'));a=json.loads(sorted(root.glob('program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json'))[-1].read_text(encoding='utf-8'))['baseline_scenario_a']
    p=json.loads(sorted(root.glob('program_driven_pilot_space_composition_v1_*/PROGRAM-A_CONTRACT.json'))[-1].read_text(encoding='utf-8'))['human_review_candidates'][0]
    return b,a,p
@lru_cache(maxsize=1)
def result():
    b,a,p=inputs();return WholeBuildingCoupledTopologySearchV1().resolve(b['site'],a,p,{'parking_required_count':3,'pedestrian_clear_width':1.2,'commercial_required':True})
def by_id(cid):return next(c for c in result()['candidates'] if c['candidate_id']==cid)

def test_core_relocation_changes_both_floors_and_never_independently():
    current=by_id('WB-NS-CURRENT-CORE');north=by_id('WB-EW-NORTH-CORE')
    assert current['core']['polygon']!=north['core']['polygon'] and north['ground_floor_changed']
    assert north['ground_floor']['core']['polygon']==north['residential_floor'].get('core',{}).get('polygon')==north['core']['polygon']
    assert north['metrics']['vertical_alignment_status']=='exact_xy_alignment'

def test_fair_ew_core_strategies_and_historical_counterexample_exist():
    assert by_id('WB-EW-CURRENT-CORE-HISTORICAL')['historical_counterexample']
    assert by_id('WB-EW-NORTH-CORE')['core_strategy']=='NORTH'
    assert by_id('WB-EW-SOUTH-CORE')['core_strategy']=='SOUTH'
    assert by_id('WB-EW-OFFSET-CORE')['core_strategy']=='OFFSET'
    assert by_id('WB-EW-TRANSVERSE-PARKING-CORE-8M')['parking_topology']=='three_transverse_stalls_east_nose'

def test_transverse_reference_has_derived_full_vehicle_field_and_exact_vertical_core():
    c=by_id('WB-EW-TRANSVERSE-PARKING-CORE-8M');g=c['ground_floor'];parcel=Polygon(result()['local_parcel_polygon'])
    stalls=[Polygon(p) for p in g['parking_stalls']];field=Polygon(g['vehicle_circulation_field'])
    assert len(stalls)==g['parking_count_generated']==3
    assert all((s.bounds[2]-s.bounds[0])>(s.bounds[3]-s.bounds[1]) for s in stalls)
    assert all(abs(s.bounds[2]-parcel.bounds[2])<1e-6 for s in stalls)
    array=stalls[0].union(stalls[1]).union(stalls[2])
    assert abs((field.bounds[3]-field.bounds[1])-(array.bounds[3]-array.bounds[1]))<1e-6
    assert g['parking_field_topology']['dimension_source']=='stall_array_plus_vehicle_turning_requirements'
    assert g['corridor_source']=='explicit_geometry_not_residual'
    assert c['core']['polygon']==g['core']['polygon']==c['residential_floor']['core']['polygon']
    assert c['residential_split']=='R-EW' and c['north_wall_offset_search']['actual_offset'] in c['north_wall_offset_search']['tested_offsets']

def test_transverse_candidate_only_enters_pareto_if_all_hard_gates_pass():
    c=by_id('WB-EW-TRANSVERSE-PARKING-CORE-8M')
    assert c['counterexample_status']=='hard_valid_but_human_architectural_review_failed'
    assert c not in result()['pareto_shortlist']

def test_v2_rotates_composable_core_prunes_equivalence_and_respects_vehicle_envelope():
    search=result()['vertical_core_transform_intelligence_v2']
    assert search['contract']=='VerticalCoreTransformIntelligenceV2'
    assert set(search['rotations_requested'])=={0,90,180,270}
    assert search['equivalent_rotations_pruned']>=1
    assert set(search['composable_components'])=={'stair','elevator','lobby'}
    assert search['selected_candidate_id'] is None
    selected=by_id(search['decision_support_candidate_ids'][0])
    assert selected['transform']['rotation_degrees'] in search['rotations_explored']
    assert selected['dependency_regeneration']=={k:'regenerated_and_re_evaluated' for k in ('parking','commercial','pedestrian','residential')}
    assert selected['vehicle_forbidden_envelope']
    assert 'core_intersects_vehicle_forbidden_envelope' not in selected['hard_rejection_reasons']
    for key in ('stair','elevator','lobby'):
        assert selected['core'][key]==selected['ground_floor']['core'][key]

def test_v2_objective_contains_architectural_quality_terms_and_moves_off_east_edge():
    selected=by_id(result()['vertical_core_transform_intelligence_v2']['decision_support_candidate_ids'][0]);objective=selected['objective']
    assert set(objective['weights'])=={'centrality','edge_penalty','commercial_preservation','pedestrian_access','residential_efficiency'}
    assert isinstance(objective['total_score'],float)
    parcel=Polygon(result()['local_parcel_polygon']);core=Polygon(selected['core']['polygon'])
    assert core.bounds[2] < parcel.bounds[2]-1e-6

def test_public_frontage_has_more_value_and_south_core_measures_loss():
    south=by_id('WB-EW-SOUTH-CORE');north=by_id('WB-EW-NORTH-CORE')
    assert south['ground_floor']['frontage_value']['public_frontage_value_exceeds_private_edge']
    assert south['metrics']['frontage_value_loss']>north['metrics']['frontage_value_loss']
    assert south['metrics']['daylight_value_loss']>0

def test_parking_and_commercial_are_revalidated_after_every_relocation():
    for c in result()['candidates']:
        g=c['ground_floor'];assert g['parking_count_generated']<=len(g['parking_stalls'])
        assert g['parking_program_satisfaction'] in ('satisfied','failed')
        assert 0<=g['commercial_coherence']<=1 and 'commercial_area' in g and 'commercial_frontage' in g

def test_large_residual_is_detected_and_program_failed_never_enters_pareto():
    assert all(c['ground_floor']['unallocated_area']>=0 and c['residential_floor'].get('residential_unallocated_area',0)>=0 for c in result()['candidates'])
    for c in result()['candidates']:
        if c['ground_floor']['unallocated_area_ratio']>.08: assert 'large_ground_floor_unallocated_area' in c['hard_rejection_reasons']
    assert all(c['hard_validation_status']=='hard_valid' for c in result()['pareto_shortlist'])
    assert not any(c['metrics']['parking_program_satisfaction']=='failed' for c in result()['pareto_shortlist'])
    assert not set(result()['pareto_shortlist_ids']) & set(result()['diagnostic_shortlist_ids'])

def test_dependency_graph_exposes_cross_floor_consequences():
    graph=result()['architectural_dependency_graph'];core=next(n for n in graph['nodes'] if n['node_id']=='core_location')
    assert 'ground_floor_commercial_geometry' in core['downstream_consequences'] and 'residential_split_feasibility' in core['downstream_consequences']

def test_no_rooms_windows_selection_or_state_mutation():
    b,a,p=inputs();before=hashlib.sha256(json.dumps((b,a,p),sort_keys=True).encode()).hexdigest();r=WholeBuildingCoupledTopologySearchV1().resolve(b['site'],a,p,{'parking_required_count':3,'pedestrian_clear_width':1.2,'commercial_required':True});after=hashlib.sha256(json.dumps((b,a,p),sort_keys=True).encode()).hexdigest()
    assert before==after and r['baseline_geometry_preserved'] and r['previous_evidence_preserved']
    assert not r['room_layout_generated'] and not r['final_windows_generated'] and not r['final_selection_performed'] and r['final_whole_building_topology'] is None
    assert not r['program_changed'] and not r['basement_deleted'] and not r['basement_removal_approved']
    assert not r['structure_executed'] and not r['bim_executed'] and not r['ifc_executed']

def test_vehicle_movement_swept_and_pedestrian_design_are_preserved_in_coupled_contract():
    for candidate in result()['candidates']:
        ground=candidate['ground_floor']
        assert ground['vehicle_movement']['contract']=='VehicleMovementPathV3'
        assert ground['vehicle_access_path'] and ground['swept_path']
        assert ground['pedestrian_access_design']['source']=='PedestrianSiteAccessDesignReasonerV1'
        assert len(ground['pedestrian_access_candidates'])>=2
        assert all(item.get('vehicle_conflict_status')!='conflict' for item in ground['pedestrian_access_candidates'] if item.get('geometry_status')=='candidate')

def test_role_first_commercial_and_functional_accounting_do_not_double_count():
    for candidate in result()['candidates']:
        ground=candidate['ground_floor'];account=ground['functional_area_accounting']
        assert abs(account['parcel_area']-account['functional_union_area']-account['free_area'])<1e-5
        assert account['double_counting_area']==0
        roles=ground['architectural_space_roles']['spaces']
        commercial=[Polygon(x['polygon']) for x in roles if x['role']=='commercial_viable']
        excluded=[Polygon(x['polygon']) for x in roles if x['role'] in ('common_service','commercially_nonviable_residual')]
        assert all(a.intersection(b).area<1e-7 for a in commercial for b in excluded)

def test_each_candidate_has_fresh_execution_trace_and_geometry_fingerprints():
    traces=[c['architectural_constraint_propagation'] for c in result()['candidates']]
    assert all(t['all_dependencies_regenerated'] and not t['candidate_state_reuse'] for t in traces)
    assert all(all(v['executed'] for v in t['executions'].values()) for t in traces)
    assert len({t['revisions']['vehicle_movement_swept_path'] for t in traces})>1
    assert result()['final_selection_performed'] is False
