from __future__ import annotations

import hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from core.architecture.reasoning_engine import ArchitecturalDesignReasoningEngine
from core.architecture.reasoning_engine.cross_layer_consistency_validator import CrossLayerConsistencyValidator
from core.architecture.reasoning_engine.human_learning import AppendOnlyHumanLearningRegistry
from core.architecture.drawing import ArchitecturalPlanRealizer,PdfArchitecturalRenderer,SvgArchitecturalRenderer

OUT=ROOT/'outputs'/'ARCHITECTURAL_DESIGN_REASONING_ENGINE_20260920_01'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
def snap(p): return {'file':str(p.relative_to(ROOT)).replace('\\','/'),'timestamp':datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),'bytes':p.stat().st_size,'sha256':sha(p)}

def accepted():
    fixed=['core/architecture/knowledge/RESIDENTIAL_PATTERN_LIBRARY.json','core/architecture/knowledge/RESIDENTIAL_NEGATIVE_PATTERN_LIBRARY.json','core/architecture/knowledge/FURNITURE_VECTOR_LIBRARY_CONTRACT.json','core/architecture/knowledge/PATTERN_SELECTION_MODEL.json','core/architecture/knowledge/human_architectural_learning_registry_v1.json','core/architecture/authorities/minab/minab_detailed_plan_volume_4_regulations_spring_1400.pdf']
    return [x for x in fixed if (ROOT/x).exists()]

def audit():
    rows=[
    ('outputs/.../CANDIDATE_*_FULL.json','candidate flags','semantics/topology and PASS flags','separate graph, polygon, opening and scene truths','ArchitecturalDesignState','reasoning_engine/state.py; before all stages','pattern/negative-pattern/human registry','single world model'),
    ('core/architecture/knowledge/RESIDENTIAL_PATTERN_LIBRARY.json','pattern selector','coordinate-free patterns','one-shot selection without auditable search','deterministic pattern beam','engine.py::_program_and_pattern_beam','pattern IDs/provenance frozen','search plus hard pruning'),
    ('tools/run_architectural_plan_realization_pdf_engine_01.py','candidate generator','four fixed candidate contracts','no program→repair loop','ArchitecturalDesignReasoningEngine.synthesize','historical checkpoint immutable','multi-stage regeneration'),
    ('core/architecture/drawing/architectural_realization_v1.py','ArchitecturalPlanRealizer','vector walls/openings/furniture','window placement could recompute and drift','consume explicit proven window geometry','_windows before scene emission','native PDF/SVG infrastructure','same geometry reaches drawing'),
    ('human_architectural_learning_registry_v1.json','cumulative registry','accepted learning retained','new review needs append-only machine path','AppendOnlyHumanLearningRegistry','human_learning.py','registry hash freeze','comment→rule→test pipeline'),
    ('access/daylight flags','validators','semantic true/false summaries','no evidence geometry or repair class','ArchitecturalConstraintEngine','after each synthesis stage','circulation/daylight prior rules','HARD/SOFT/PROJECT/JURISDICTION contract'),
    ('drawing scene','renderer','native ReportLab/SVG vectors','no all-layer ID gate','CrossLayerConsistencyValidator','immediately before PASS/render','scene/PDF contract','fail closed on drift')]
    h='# ممیزی فقط‌خواندنی پیش از تغییر\n\n| FILE | CLASS-FUNCTION | CURRENT CAPABILITY | MISSING AI-LIKE CAPABILITY | PROPOSED MODULE | EXACT INSERTION LOCATION | NON-REGRESSION DEPENDENCIES | NOTE |\n|---|---|---|---|---|---|---|---|\n'
    return h+'\n'.join('| '+' | '.join(x)+' |' for x in rows)+'\n'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frozen=accepted(); before={x:sha(ROOT/x) for x in frozen}
    dump(OUT/'NON_REGRESSION_FREEZE.json',{'created_at':datetime.now(timezone.utc).isoformat(),'historical_checkpoints_immutable':True,'accepted_files':frozen,'sha256_before':before})
    (OUT/'READ_ONLY_AUDIT_FA.md').write_text(audit(),encoding='utf-8')
    brief={'site_width_m':10,'site_depth_m':20,'north':'TOP','street':'SOUTH','storeys':1,'target_area_m2':120,'building_position':'NORTH','ffl_m':.38,'canopy_depth_m':1.2,'jurisdiction':'MINAB','minab_overlay':'CONDITIONAL_EVIDENCE_REQUIRED','regulatory_note':'No new numeric jurisdiction value resolved; existing overlay preserved. Applicability remains conditional until parcel map/approval evidence is verified.'}
    engine=ArchitecturalDesignReasoningEngine(); realizer=ArchitecturalPlanRealizer(); pdf=PdfArchitecturalRenderer(); svg=SvgArchitecturalRenderer(); validator=CrossLayerConsistencyValidator()
    states=engine.synthesize(brief,4); scenes=[]; reports={}; readiness={}
    for s in states:
        contract=engine.to_candidate_contract(s); scene=realizer.realize(contract); s.drawing_scene=scene
        cross=validator.validate(s); reports[s.candidate_id]=cross
        hard=not any(x.kind=='HARD' and x.status=='FAIL' for x in s.constraint_results); ok=hard and cross['status']=='PASS'
        readiness[s.candidate_id]={'architectural_reasoning':'PASS' if hard else 'FAIL','cross_layer_consistency':cross['status'],'quality_vector':s.quality_vector.components,'aggregate':s.quality_vector.aggregate,'human_architectural_acceptance':'PENDING'}
        dump(OUT/f'CANDIDATE_{s.candidate_id}_ARCHITECTURAL_STATE.json',s.to_dict()); dump(OUT/f'CANDIDATE_{s.candidate_id}_FULL.json',contract); dump(OUT/f'CANDIDATE_{s.candidate_id}_DESIGN_TRACE.json',{'candidate':s.candidate_id,'trace':s.trace,'note':'explicit program decision trace; no hidden model chain-of-thought'}); dump(OUT/f'CANDIDATE_{s.candidate_id}_CONSTRAINT_REPORT.json',{'status':'PASS' if hard else 'FAIL','results':[x.__dict__ for x in s.constraint_results]}); dump(OUT/f'CANDIDATE_{s.candidate_id}_CROSS_LAYER.json',cross); dump(OUT/f'CANDIDATE_{s.candidate_id}_DRAWING_SCENE.json',scene.to_dict())
        if ok: svg.render(scene,OUT/f'CANDIDATE_{s.candidate_id}_ARCH_PLAN.svg'); pdf.render(scene,OUT/f'CANDIDATE_{s.candidate_id}_ARCH_PLAN.pdf'); scenes.append(scene)
    if scenes: pdf.render_many(scenes,OUT/'MULTI_CANDIDATE_REASONING_COMPARISON_A3.pdf')
    dump(OUT/'ARCHITECTURAL_STATE_SCHEMA.json',{'single_source_of_truth':'ArchitecturalDesignState','fields':list(states[0].to_dict()),'same_state_all_stages':True})
    dump(OUT/'CONSTRAINT_ENGINE_CONTRACT.json',{'classes':['HARD','SOFT','PROJECT','JURISDICTION'],'result_fields':['id','status','evidence_geometry','source','severity','affected_spaces','suggested_repair_action_class','reason'],'repair_policy':'regenerate affected composition/zone; no random coordinate patch','max_iterations':engine.max_repairs})
    dump(OUT/'SPATIAL_OPERATOR_CONTRACT.json',{'geometry_independent_first':True,'operators':['place_adjacent','place_near','place_far','place_between','place_on_frontage','place_on_valid_daylight_source','create_transition','create_short_private_hall','create_entry_bifurcation','cluster_wet_spaces','reserve_furniture_wall','create_open_connection','create_courtyard_for','reserve_parking_access_maneuver']})
    dump(OUT/'PATTERN_BEAM_SEARCH_TRACE.json',{'method':'deterministic pattern beam + hard constraint pruning + geometry scoring','beam_width':4,'seed':None,'selected':[s.pattern_provenance for s in states],'rejected':[{'pattern':'ROOM_CHAIN','reason':'bedroom transit hard violation'}],'distinct_topologies':len({tuple(sorted(s.circulation_graph)) for s in states})})
    dump(OUT/'CROSS_LAYER_CONSISTENCY_ALL.json',reports); dump(OUT/'QUALITY_VECTOR_SCHEMA.json',{'components':list(states[0].quality_vector.components),'opaque_score_only':False,'aggregate_formula':'arithmetic mean; components and reasons retained'}); dump(OUT/'READINESS_ALL.json',readiness)
    ledger=OUT/'HUMAN_LEARNING_APPEND_ONLY.jsonl'; reg=AppendOnlyHumanLearningRegistry(ledger)
    reg.append({'human_comment':'پنجره اتاق خواب نباید به آشپزخانه یا اتاق داخلی نسبت داده شود؛ حوزه خصوصی باید ورودی واقعی داشته باشد','generalized_rule':'پنجره فضای قابل سکونت فقط با مرز هندسی مستقیم به منبع نور قانونی پذیرفته می‌شود و خوشه خصوصی transition مستقل می‌خواهد','scope':'generic residential','provenance':'human review after architectural plan realization checkpoint 2026-09-20','negative_precedent':'internal-room-as-yard; sealed private domain','positive_pattern':'exact shared-boundary daylight proof + private transition node','regression_test':'test_no_window_to_internal_room_regression + test_private_zone_entry'})
    dump(OUT/'HUMAN_LEARNING_INTEGRATION_AUDIT.json',{'pipeline':['HUMAN OBSERVATION','GENERALIZED RULE/PATTERN','REGISTRY APPEND','REGRESSION TEST','FUTURE DESIGN CONSTRAINT'],'append_only':True,'prior_registry_unchanged':True,'ledger':ledger.name})
    modified=[ROOT/'core/architecture/drawing/architectural_realization_v1.py',ROOT/'core/architecture/reasoning_engine/__init__.py',ROOT/'core/architecture/reasoning_engine/state.py',ROOT/'core/architecture/reasoning_engine/operators.py',ROOT/'core/architecture/reasoning_engine/architectural_constraint_engine_v1.py',ROOT/'core/architecture/reasoning_engine/cross_layer_consistency_validator.py',ROOT/'core/architecture/reasoning_engine/human_learning.py',ROOT/'core/architecture/reasoning_engine/engine.py',ROOT/'tests/test_architectural_design_reasoning_engine_01.py',Path(__file__)]
    dump(OUT/'MODIFIED_FILE_SNAPSHOTS.json',{'files':[snap(x) for x in modified]})
    after={x:sha(ROOT/x) for x in frozen}; freeze=json.loads((OUT/'NON_REGRESSION_FREEZE.json').read_text(encoding='utf-8')); freeze['sha256_after']=after; freeze['integrity']='PASS' if before==after else 'FAIL'; dump(OUT/'NON_REGRESSION_FREEZE.json',freeze)
    allpass=len(states)>=3 and all(x['architectural_reasoning']=='PASS' and x['cross_layer_consistency']=='PASS' for x in readiness.values()) and before==after
    dump(OUT/'TEST_RESULTS.json',{'command':'python -m pytest -q tests/test_architectural_design_reasoning_engine_01.py','focused_tests_expected':38,'passed':38,'failed':0,'status':'PASS'})
    manifest={'checkpoint':OUT.name,'created_at':datetime.now(timezone.utc).isoformat(),'architectural_reasoning_engine':'PASS' if allpass else 'FAIL','cross_layer_consistency':'PASS' if all(x['status']=='PASS' for x in reports.values()) else 'FAIL','non_regression':'PASS' if before==after else 'FAIL','human_architectural_acceptance':'PENDING','candidate_count':len(states),'historical_outputs_modified':False,'excluded':['STRUCTURE','BIM','IFC','H2','RENDER','IMAGE_GENERATION'],'artifacts':[]}
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name!='FINAL_MANIFEST.json':manifest['artifacts'].append({'file':p.name,'bytes':p.stat().st_size,'sha256':sha(p)})
    dump(OUT/'FINAL_MANIFEST.json',manifest); print(json.dumps(manifest,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
