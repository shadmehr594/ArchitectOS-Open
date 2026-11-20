import hashlib,json
from functools import lru_cache
from pathlib import Path
from core.architecture.reasoning.minab_residential_architectural_rules_v1 import MinabResidentialArchitecturalRulesV1
from core.architecture.reasoning.projection_and_overhang_opportunity_intelligence_v1 import ProjectionAndOverhangOpportunityIntelligenceV1
from core.architecture.reasoning.residential_floor_access_daylight_topology_v2 import ResidentialFloorAccessDaylightTopologyV2
ROOT=Path(__file__).resolve().parents[2]
def inputs():
 bp=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];root=bp.parent;b=json.loads(bp.read_text());a=json.loads(sorted(root.glob('program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json'))[-1].read_text())['baseline_scenario_a'];p=json.loads(sorted(root.glob('program_driven_pilot_space_composition_v1_*/PROGRAM-A_CONTRACT.json'))[-1].read_text())['human_review_candidates'][0];return b,a,p
@lru_cache(maxsize=1)
def result():
 b,a,p=inputs();return ResidentialFloorAccessDaylightTopologyV2().resolve(b['site'],a,p,{'jurisdiction':'Minab','allowed_floor_count':5})
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def test_all_stair_and_elevator_walk_paths_and_explicit_doors_exist():
 for c in result()['human_review_candidates']:
  g=c['residential_common_access_graph'];proof=g['walk_path_proofs'];assert all(proof[k] for k in ('stair_to_unit_1','stair_to_unit_2','elevator_to_unit_1','elevator_to_unit_2'));assert g['paths_stay_common_until_unit_threshold'];assert len(g['unit_entry_doors'])==2;assert all(d['door_face'] and d['door_swing_or_clearance_zone'] for d in g['unit_entry_doors'])
def test_shared_court_serves_both_units_and_maintenance_is_common():
 for c in result()['human_review_candidates']:
  court=c['shared_daylight_court'];maintenance=c['shared_daylight_court_maintenance_access'];assert court['space_type']=='COMMON_SHARED_DAYLIGHT_COURT' and court['court_serves_both_units'];assert court['unit_1_daylight_edge_length']>0 and court['unit_2_daylight_edge_length']>0;assert maintenance['maintenance_source']=='COMMON' and not maintenance['private_unit_crossing'];assert maintenance['maintenance_door']['door_face']
def test_privacy_distance_and_installation_height_are_semantically_distinct():
 r=result()['minab_rules']['rules'];assert r['opposing_independent_unit_windows_min_distance']['value']==3.0;assert r['opposing_unit_windows_privacy_height']['value']==1.70;assert r['opposing_unit_windows_privacy_height']['rule_status']=='authoritative_clause_semantic_normalization_required'
def test_vertical_extent_is_rule_driven_and_no_caretaker_is_invented():
 for c in result()['human_review_candidates']:
  v=c['daylight_court_vertical_extent'];assert v['selected_extent'] is None and v['regulatory_vertical_extent_status']=='pending_rule_resolution';assert {x['extent_type'] for x in v['alternatives']}=={'full_height_lightwell','residential_level_daylight_void'};assert not v['caretaker_unit_generated']
 assert not result()['caretaker_unit_requested'] and not result()['caretaker_unit_generated']
def test_minab_projection_is_jurisdiction_specific_user_optional_and_exact_10m_pending():
 rules=MinabResidentialArchitecturalRulesV1().resolve();e=ProjectionAndOverhangOpportunityIntelligenceV1();off=e.resolve('Minab',10,rules,{'allow_public_road_projection':False});other=e.resolve('OtherCity',10,rules,{'allow_public_road_projection':True});on=e.resolve('Minab',10,rules,{'allow_public_road_projection':True});assert off['public_road_projection']['projection_status']=='projection_disabled_by_user';assert other['public_road_projection']['projection_status']=='not_applicable_outside_jurisdiction';assert on['public_road_projection']['projection_width']==.8;assert on['public_road_projection']['projection_status']=='pending_exact_boundary_condition_and_local_approval_interpretation'
def test_projection_clear_height_inside_values_and_over20_variants():
 rules=MinabResidentialArchitecturalRulesV1().resolve();e=ProjectionAndOverhangOpportunityIntelligenceV1();failed=e.resolve('Minab',12,rules,{'allow_public_road_projection':True},3.4,0);passed=e.resolve('Minab',12,rules,{'allow_public_road_projection':True},3.6,0);assert failed['public_road_projection']['minimum_clear_height']==3.5 and failed['public_road_projection']['projection_geometry_status']=='vertical_clearance_failed';assert passed['public_road_projection']['projection_geometry_status']=='vertical_clearance_passed';assert passed['inside_property_projection']['maximum_width']==1.2 and passed['inside_property_projection']['minimum_clear_height']==2.7;assert passed['over_20m_rule_variants']['value']==[1.0,1.2] and passed['over_20m_rule_variants']['rule_status']=='requires_clause_applicability_resolution'
def test_projection_and_no_projection_pairs_exist_without_becoming_approved():
 r=result();
 for family in ('R-EW','R-NS','R-HYBRID'):
  modes={c['projection_mode'] for c in r['human_review_candidates'] if c['split_family']==family};assert modes=={'projection_disabled','projection_candidate_enabled'}
 for c in r['human_review_candidates']:
  if c['projection_mode'].endswith('enabled'):assert c['projection_opportunity']['public_road_projection']['projection_status'].startswith('pending_')
def test_no_rooms_windows_final_selection_or_state_mutation():
 b,a,p=inputs();before=digest((b,a,p));r=ResidentialFloorAccessDaylightTopologyV2().resolve(b['site'],a,p,{'jurisdiction':'Minab'});assert before==digest((b,a,p));assert not r['room_layout_generated'] and not r['final_windows_generated'] and not r['final_selection_performed'];assert r['final_residential_topology'] is None and r['baseline_geometry_preserved'];assert not r['program_changed'] and not r['basement_deleted'] and not r['basement_removal_approved'];assert not r['structure_executed'] and not r['bim_executed'] and not r['ifc_executed'] and not r['render_pipeline_executed']
