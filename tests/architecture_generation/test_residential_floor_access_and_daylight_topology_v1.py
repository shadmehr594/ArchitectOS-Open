import hashlib,json
from functools import lru_cache
from pathlib import Path
from shapely.geometry import Polygon
from core.architecture.reasoning.residential_floor_access_and_daylight_topology_v1 import ResidentialFloorAccessAndDaylightTopologyV1
ROOT=Path(__file__).resolve().parents[2]
def inputs():
 bp=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];root=bp.parent;b=json.loads(bp.read_text());a=json.loads(sorted(root.glob('program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json'))[-1].read_text())['baseline_scenario_a'];p=json.loads(sorted(root.glob('program_driven_pilot_space_composition_v1_*/PROGRAM-A_CONTRACT.json'))[-1].read_text())['human_review_candidates'][0];return b,a,p
@lru_cache(maxsize=1)
def result():
 b,a,p=inputs();return ResidentialFloorAccessAndDaylightTopologyV1().resolve(b['site'],a,p)
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def test_real_parcel_preserves_unresolved_planning_inputs_without_coverage_leakage():
 r=result();assert r['source_parcel'][0]==[9.495348,22.127313] and r['source_road_width']==10.0;z=r['zoning_context'];assert z['ground_coverage_mode']=='unresolved_human_input_required';assert z['ground_coverage_percent'] is None and z['allowed_far'] is None;assert z['human_input_required']==['allowed_far','max_site_coverage'];assert z['open_space_per_unit_requirement']['current_case_status']=='unresolved_pending_project_coverage_input';assert z['lightwell_requirement']['current_case_status']=='applicable_independently_of_site_open_space'
def test_authoritative_lightwell_geometry_remains_active_with_provenance():
 r=result();rule=r['minab_rules']['rules']['main_space_lightwell_min_area'];assert rule['value']==12.0 and rule['source_document'].startswith('طرح تفصیلی شهر میناب');assert all(c['lightwell']['area']>=12 and c['lightwell']['minimum_width']>=3 for c in r['human_review_candidates']);assert all(c['lightwell']['natural_airflow_required'] for c in r['human_review_candidates'])
def test_private_neighbor_edges_have_no_openings_or_terraces():
 r=result();assert r['zoning_context']['edge_context']['north']=='adjacent_private_parcel' and r['zoning_context']['edge_context']['west']=='adjacent_private_parcel'
 for c in r['human_review_candidates']:
  assert c['north_edge_opening_status'].startswith('forbidden') and c['west_edge_opening_status'].startswith('forbidden');assert all(t['terrace_open_edge'] not in ('north_private_neighbor','west_private_neighbor') for t in c['terraces'])
def test_every_unit_has_user_required_private_terrace_separate_from_lightwell():
 for c in result()['human_review_candidates']:
  assert len(c['terraces'])==2 and all(t['terrace_area']>0 and t['requirement_source']=='user_design_requirement' for t in c['terraces']);assert all(Polygon(t['terrace_polygon']).intersection(Polygon(c['lightwell']['polygon'])).area<1e-6 for t in c['terraces'])
def test_all_split_families_exist_and_corridor_like_ew_is_penalized():
 r=result();assert set(r['families_explored'])=={'R-EW','R-NS','R-HYBRID'};ew=[c for c in r['candidates'] if c['split_family']=='R-EW'];assert ew and all(any('corridor_like' in p for p in c['architectural_quality_penalties']) for c in ew)
def test_stair_elevator_and_two_independent_entries_are_resolved():
 for c in result()['human_review_candidates']:
  assert c['stair']['stair_start_point']!=c['stair']['stair_end_point'];assert c['stair']['stair_arrival_status']=='resolved';assert c['stair_vertical_alignment_status']=='aligned_to_pilot_reference';assert c['elevator_vertical_alignment_status']=='aligned_to_pilot_reference';assert c['elevator']['elevator_front_clear_zone'];assert len({tuple(u['entry_point']) for u in c['unit_envelopes']})==2;assert c['common_corridor_termination_status']=='terminates_at_last_unit_entry'
def test_no_rooms_or_downstream_execution_and_state_is_preserved():
 b,a,p=inputs();before=digest((b,a,p));r=ResidentialFloorAccessAndDaylightTopologyV1().resolve(b['site'],a,p);assert before==digest((b,a,p));assert not r['room_layout_generated'];assert not r['bedroom_polygons'] and not r['living_polygons'] and not r['kitchen_polygons'];assert r['baseline_geometry_preserved'];assert not r['program_changed'] and not r['basement_deleted'] and not r['basement_removal_approved'];assert not r['structure_executed'] and not r['bim_executed'] and not r['ifc_executed'] and not r['render_pipeline_executed'];assert not r['final_selection_performed']
