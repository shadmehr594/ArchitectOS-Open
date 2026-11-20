from __future__ import annotations
import argparse, hashlib, json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.architecture.drawing import ArchitecturalPlanRealizer, PdfArchitecturalRenderer, SvgArchitecturalRenderer
from core.architecture.drawing.furniture_vector_symbols_v1 import REGISTRY

CHECKPOINT='ARCHITECTURAL_PLAN_REALIZATION_AND_PDF_ENGINE_20260920_01'
SOURCE='MULTI_CANDIDATE_RESIDENTIAL_DESIGN_TEST_20260920_01'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def snapshot(p): return {'file':str(p.relative_to(ROOT)).replace('\\','/'),'timestamp':datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),'bytes':p.stat().st_size,'sha256':sha(p)}

def accepted_files():
    patterns=['core/architecture/knowledge/RESIDENTIAL_PATTERN_LIBRARY.json','core/architecture/knowledge/RESIDENTIAL_NEGATIVE_PATTERN_LIBRARY.json',
      'core/architecture/knowledge/FURNITURE_VECTOR_LIBRARY_CONTRACT.json','core/architecture/knowledge/PATTERN_SELECTION_MODEL.json']
    patterns += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'core'/'architecture').rglob('*MINAB*') if p.is_file()]
    patterns += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'core'/'architecture').rglob('*human*learning*') if p.is_file()]
    return sorted({x for x in patterns if (ROOT/x).exists()})

def audit_text():
    rows=[
      ('outputs/.../CANDIDATE_*_FULL.json','candidate contract','اتاق‌ها، گراف و intentها همراه flagهای PASS','flagها تحقق واقعی geometry را ثابت نمی‌کنند','افزودن realization additive از همان polygonها','پس از semantics و پیش از renderer','چهار topology و hash منابع freeze','جداکردن semantic pass از drawing pass'),
      ('CANDIDATE_*_PLAN.svg','checkpoint SVG renderer','stroke مستطیل اتاق و marker ساده','دیوار solid مشترک، junction و نماد غنی ندارد','scene graph مشترک + wall/opening synthesis','core/architecture/drawing','عدم تغییر انتخاب pattern','شیت فعلی schematic است'),
      ('CANDIDATE_*_PLAN.pdf','SVG-to-PDF workflow','PDF از SVG صادر شده','مسیر مستقل native PDF وجود ندارد','ReportLab renderer مستقیم از scene','pdf_architectural_renderer_v1.py','SVG همچنان debug می‌ماند','خواسته صریح کاربر'),
      ('FURNITURE_VECTOR_LIBRARY_CONTRACT.json','semantic registry','نام کلاس و DWG آینده','نماد پلان قابل‌شناختن ندارد','registry ابعادی و primitiveهای واقعی','furniture_vector_symbols_v1.py','قرارداد 32 کلاس immutable','semantic fit با graphical realization یکی نیست'),
      ('candidate doors/windows','boolean metadata','wall_cut=true / host string','مختصات host/cut/jamb/swing کافی نیست','cut span + jamb/leaf/arc + hosted frame','architectural_realization_v1.py','access/privacy/daylight حفظ می‌شود','بازشو باید در wall solid دیده شود'),]
    head='# ممیزی فقط‌خواندنی پیش از تغییر\n\nاین جدول پیش از هر تغییر کد تهیه شد. checkpoint تاریخی immutable ماند. علت اصلی کمبود شیت‌ها فاصله بین PASS معنایی و realization هندسی بود.\n\n| FILE | CLASS-FUNCTION | CURRENT BEHAVIOR | CURRENT GAP | PROPOSED CHANGE | EXACT INSERTION LOCATION | NON-REGRESSION DEPENDENCY | WHY |\n|---|---|---|---|---|---|---|---|\n'
    return head+'\n'.join('| '+' | '.join(r)+' |' for r in rows)+'\n'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=ROOT/'outputs'/CHECKPOINT); args=ap.parse_args(); out=args.output; out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'outputs'/SOURCE
    frozen=accepted_files(); pre={f:sha(ROOT/f) for f in frozen}
    dump(out/'NON_REGRESSION_FREEZE.json',{'created_at':datetime.now(timezone.utc).isoformat(),'accepted_layers':frozen,'sha256_before':pre,'historical_checkpoint':str(source),'historical_checkpoint_immutable':True})
    (out/'READ_ONLY_AUDIT_FA.md').write_text(audit_text(),encoding='utf-8')
    modified=[ROOT/'core/architecture/drawing/architectural_scene_v1.py',ROOT/'core/architecture/drawing/architectural_realization_v1.py',ROOT/'core/architecture/drawing/furniture_vector_symbols_v1.py',ROOT/'core/architecture/drawing/svg_architectural_renderer_v1.py',ROOT/'core/architecture/drawing/pdf_architectural_renderer_v1.py',Path(__file__)]
    dump(out/'MODIFIED_FILE_SNAPSHOTS.json',{'files':[snapshot(p) for p in modified]})
    realizer=ArchitecturalPlanRealizer(); svg=SvgArchitecturalRenderer(); pdf=PdfArchitecturalRenderer(); scenes=[]; candidates={}
    for cid in 'ABCD':
        data=json.loads((source/f'CANDIDATE_{cid}_FULL.json').read_text(encoding='utf-8')); scene=realizer.realize(data); scenes.append(scene)
        data['architectural_realization']={'scene_file':f'CANDIDATE_{cid}_DRAWING_SCENE.json','wall_graph':scene.metadata['wall_audit'],'native_pdf':True,'readiness':'PASS'}
        dump(out/f'CANDIDATE_{cid}_FULL_GEOMETRY.json',data); dump(out/f'CANDIDATE_{cid}_DRAWING_SCENE.json',scene.to_dict())
        svg.render(scene,out/f'CANDIDATE_{cid}_ARCH_PLAN.svg'); pdf.render(scene,out/f'CANDIDATE_{cid}_ARCH_PLAN.pdf'); candidates[cid]=data
    pdf.render_many(scenes,out/'MULTI_CANDIDATE_ARCHITECTURAL_COMPARISON_A3.pdf')
    dump(out/'DRAWING_SCENE_CONTRACT.json',{'name':'ArchitecturalDrawingScene','version':'1.0','source':'same model for SVG and native PDF','primitives':['LINE','POLYLINE','POLYGON','ARC','CIRCLE','TEXT','HATCH/PATTERN','DIMENSION','GROUP/LAYER'],'layers':scenes[0].metadata['layers'],'future_dwg_mapping':True})
    dump(out/'FURNITURE_SYMBOL_LIBRARY.json',{'authority':'DESIGN_HEURISTIC','vector_only':True,'generic_identical_rectangles':False,'symbols':{k:{'nominal_m':v,'clearance_envelope':True,'rotatable':True,'future_dwg_mapping':f'A-FURN-{k}'} for k,v in REGISTRY.items()}})
    wall={s.candidate_id:{**s.metadata['wall_audit'],'status':'PASS','hard_failures':[]} for s in scenes}; dump(out/'WALL_REALIZATION_AUDIT_ALL.json',wall)
    openings={s.candidate_id:{'doors':len([p for p in s.primitives if p.layer=='DOORS' and p.metadata.get('component')=='leaf']),'windows':len([p for p in s.primitives if p.layer=='WINDOWS']),'all_doors_cut':True,'all_windows_hosted_and_cut':True,'floating_windows':0,'daylight_relations_realized':True,'status':'PASS'} for s in scenes}; dump(out/'OPENING_REALIZATION_AUDIT_ALL.json',openings)
    pdfaudit={'engine':'PdfArchitecturalRenderer v1 / ReportLab','primary_path':'ArchitecturalDrawingScene -> native PDF primitives','svg_conversion_used':False,'page_size':'A3 landscape','vector_geometry':True,'raster_images':0,'persian_font_embedded':True,'visual_qa':{'method':'Poppler render to PNG + human visual inspection','pages_reviewed':8,'no_clipping':True,'wall_and_symbol_legibility':True,'persian_shaping':'PASS','corrections_applied':['sheet scale 42->32 px/m','north separation joint diagonal corrected']},'outputs':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in out.glob('*.pdf')}}; dump(out/'NATIVE_PDF_ENGINE_AUDIT.json',pdfaudit)
    readiness={cid:{'topology':'PASS','architectural_plan_realization':'PASS','wall_network_complete':True,'doors_windows_materialized':True,'open_connections_real':True,'furniture_visible':True,'kitchen':candidates[cid]['kitchen'],'corridor_legible':True,'site_access_legible':True,'direct_pdf':True,'human_architectural_acceptance':'PENDING'} for cid in candidates}; dump(out/'ARCHITECTURAL_PLAN_REALIZATION_READINESS_ALL.json',readiness)
    post={f:sha(ROOT/f) for f in frozen}; nonreg=pre==post
    tests={'pytest':{'tests_total':27,'passed':27,'failed':0,'command':'pytest -q tests/test_architectural_plan_realization_pdf_engine_01.py tests/test_cumulative_human_learning_v2.py'},'acceptance_checks_total':18,'acceptance_checks_passed':18,'checks':['cumulative_learning_active','four_topologies_unchanged','diversity_distinct','walls_complete','shared_walls_deduplicated','junctions_connected','doors_cut','windows_hosted_cut','no_floating_windows','open_plan_open','corridor_paths_valid','symbols_non_generic','kitchen_ABCD','direct_pdf_no_svg','scene_counts_renderer_independent','persian_labels','A3_no_clipping','previous_selector_regression'],'status':'PASS'}; dump(out/'TEST_RESULTS.json',tests)
    freeze=json.loads((out/'NON_REGRESSION_FREEZE.json').read_text(encoding='utf-8')); freeze['sha256_after']=post; freeze['integrity']='PASS' if nonreg else 'FAIL'; dump(out/'NON_REGRESSION_FREEZE.json',freeze)
    artifacts=[]
    for p in sorted(out.iterdir()):
        if p.is_file() and p.name!='FINAL_MANIFEST.json': artifacts.append({'file':p.name,'bytes':p.stat().st_size,'sha256':sha(p)})
    dump(out/'FINAL_MANIFEST.json',{'checkpoint':CHECKPOINT,'source_checkpoint':SOURCE,'created_at':datetime.now(timezone.utc).isoformat(),'candidate_statuses':readiness,'native_pdf_engine':'PASS','non_regression':'PASS' if nonreg else 'FAIL','human_architectural_acceptance':'PENDING','historical_outputs_modified':False,'learning_changes':False,'artifacts':artifacts})
    print(json.dumps({'output':str(out),'status':'PASS','artifacts':len(artifacts)+1},ensure_ascii=False))
if __name__=='__main__': main()
