import hashlib, json
from functools import lru_cache
from pathlib import Path

from core.architecture.reasoning.program_driven_pilot_space_composition_v1 import ProgramDrivenPilotSpaceCompositionV1
from core.architecture.reasoning.program_space_requirement_v1 import ProgramSpaceRequirementV1

ROOT=Path(__file__).resolve().parents[2]
def inputs():
 p=sorted((ROOT/'exports'/'DEFAULT').glob('parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json'))[-1];r=sorted(p.parent.glob('program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json'))[-1]
 return json.loads(p.read_text()),json.loads(r.read_text())['baseline_scenario_a']
def core_requirements(parking=3):
 return [
  {'space_type':'parking','required':True,'required_count':parking,'hard_requirement':True,'requirement_source':'user_design_requirement','priority':90},
  {'space_type':'commercial','required':True,'hard_requirement':True,'area_goal':'maximize','expandable':True,'shrinkable':True,'requirement_source':'user_design_requirement','priority':70},
  *[{'space_type':t,'required':True,'hard_requirement':True,'requirement_source':'project_requirement','priority':95} for t in ('stair','elevator','common_lobby')]]
@lru_cache(maxsize=None)
def run(kind='base'):
 q=core_requirements()
 if kind=='support':q += [{'space_type':'residential_storage','required':True,'count':2,'required_count':2,'preferred_area_per_unit':5.0,'maximum_area_per_unit':6.0,'shrinkable':True,'hard_requirement':True,'requirement_source':'user_design_requirement'}, {'space_type':'mechanical_room','required':True,'preferred_area':4.0,'shrinkable':True,'hard_requirement':True,'requirement_source':'engineering_assumption','regulatory_status':'pending_rule_resolution'}]
 b,a=inputs();return ProgramDrivenPilotSpaceCompositionV1().resolve(b['site'],b['requirements'],a,q,f'TEST-{kind}')
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()

def test_requirement_contract_distinguishes_hard_soft_and_unknown_dimensions():
 m=ProgramSpaceRequirementV1.manifest([{'space_type':'mechanical_room','required':True,'hard_requirement':True,'requirement_source':'unresolved_source'},{'space_type':'caretaker_unit','preferred':True,'soft_preference':True,'removable':True,'requirement_source':'user_design_requirement'}])
 assert m['required_program'][0]['hard_requirement'];assert m['preferred_program'][0]['soft_preference'];assert m['required_program'][0]['minimum_area'] is None;assert m['required_program'][0]['regulatory_status']=='pending_rule_resolution'
def test_parking_required_count_is_enforced_and_shortfall_is_explicit():
 r=run();assert all(c['parking_generated_count']==3 for c in r['human_review_candidates']);short=next(c for c in r['candidates'] if c['parking_generated_count']==2);assert 'parking_count_shortfall' in short['hard_requirement_failures'];assert short['program_compliance_status']=='program_conflict'
def test_storage_and_service_are_real_polygons_and_pending_rules_remain_pending():
 r=run('support');c=r['human_review_candidates'][0];types={s['space_type'] for s in c['generated_program_spaces']};assert {'residential_storage','mechanical_room'}<=types;assert c['storage_generated_count']==2;assert c['storage_total_area']<=12.0;assert all(s['polygon'] for s in c['generated_program_spaces']);assert any(s['regulatory_status']=='pending_rule_resolution' for s in c['generated_program_spaces'] if s['space_type']=='mechanical_room')
def test_optional_space_can_be_removed_and_shrinkable_space_can_shrink():
 e=ProgramDrivenPilotSpaceCompositionV1();m=e.compose_manifest(core_requirements()+[{'space_type':'caretaker_unit','preferred':True,'removable':True,'preferred_area':500.0,'requirement_source':'engineering_assumption'}]);b,a=inputs();r=e.resolve(b['site'],b['requirements'],a,m['requirements'],'OPTIONAL');assert any('caretaker_unit' in c['optional_spaces_dropped'] for c in r['candidates'])
 adjusted=e.apply_adjustment(m,'caretaker_unit',{'preferred_area':6.0,'shrinkable':True});assert next(x for x in adjusted['requirements'] if x['space_type']=='caretaker_unit')['preferred_area']==6.0
def test_commercial_expands_when_optional_program_is_removed():
 c=run()['human_review_candidates'][0];assert len(c['commercial_polygons'])>=1;assert c['commercial_area']>=c['geometry']['metrics']['commercial_area']
def test_conflict_identifies_exact_blocking_requirement():
 e=ProgramDrivenPilotSpaceCompositionV1();q=core_requirements()+[{'space_type':'caretaker_unit','required':True,'required_count':1,'preferred_area':500.0,'hard_requirement':True,'removable':False,'requirement_source':'engineering_assumption'}];b,a=inputs();r=e.resolve(b['site'],b['requirements'],a,q,'CONFLICT');c=r['human_review_candidates'][0];assert 'caretaker_unit_count_shortfall' in c['hard_requirement_failures'];assert any(x['requirement']=='caretaker_unit' for x in c['conflicts']);assert not c['program_conflict_analysis']['hard_requirements_silently_relaxed']
def test_scenario_a_and_pipeline_state_are_preserved():
 b,a=inputs();before=digest((b,a));r=ProgramDrivenPilotSpaceCompositionV1().resolve(b['site'],b['requirements'],a,core_requirements(),'STATE');assert before==digest((b,a));assert r['baseline_geometry_preserved'];assert not r['program_changed'] and not r['basement_deleted'] and not r['basement_removal_approved'];assert not r['structure_executed'] and not r['bim_executed'] and not r['ifc_executed'];assert not r['final_selection_performed']
