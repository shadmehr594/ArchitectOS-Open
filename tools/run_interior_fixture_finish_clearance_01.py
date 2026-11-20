from __future__ import annotations

import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from core.architecture.drawing import (ArchitecturalDrawingScene, PdfArchitecturalRenderer, SvgArchitecturalRenderer,
    SYMBOL_LIBRARY, contracts, InteriorFixtureFinishValidator, FurnitureClearanceValidator, add_review_graphics)

OUT=ROOT/'outputs'/'INTERIOR_FIXTURE_FINISH_AND_CLEARANCE_LAYER_20260921_01'
SOURCE=ROOT/'outputs'/'ARCHITECTURAL_SYMBOL_LIBRARY_AND_PLAN_GRAPHICS_20260920_01'
ORIGINAL_SNAPSHOTS=[
 {"file":"core/architecture/drawing/architectural_scene_v1.py","bytes":1597,"last_write_time_utc":"2026-09-20T19:14:41.2067472Z","sha256":"6fbda000832d5575f9c5dbf1e81bdc399524bd9b243153ae7bf27188ca061a96"},
 {"file":"core/architecture/drawing/architectural_symbol_library_v1.py","bytes":9199,"last_write_time_utc":"2026-09-20T20:31:35.8681776Z","sha256":"2e0bb3d9c77d25051850700beb303610efe9ba609ce169ec5a6ae3dec5beb5ef"},
 {"file":"core/architecture/drawing/furniture_placement_validator_v1.py","bytes":1514,"last_write_time_utc":"2026-09-20T20:31:36.7625760Z","sha256":"ec1e00e4beb2dd59fea8eedf1aa61de558081ad55156f70610a921cce395adad"},
 {"file":"core/architecture/drawing/architectural_realization_v1.py","bytes":13740,"last_write_time_utc":"2026-09-20T20:37:47.2381929Z","sha256":"9aa41ac0249dea731f8f3737bd80773b5fdaeccc5cab539782c56d59b042a2f5"},
 {"file":"core/architecture/drawing/svg_architectural_renderer_v1.py","bytes":7580,"last_write_time_utc":"2026-09-20T20:32:11.9624566Z","sha256":"6dcb65a0be7c6ca753ee91dbde50f388a154ad4eec93f412594173dc602a955e"},
 {"file":"core/architecture/drawing/pdf_architectural_renderer_v1.py","bytes":7584,"last_write_time_utc":"2026-09-20T20:32:12.8434293Z","sha256":"9f9ed07008b436abe47b35fae4bcc6a6479fa60a84cf7aed73e876126e0275b3"},
 {"file":"core/architecture/drawing/__init__.py","bytes":791,"last_write_time_utc":"2026-09-20T20:33:36.8832428Z","sha256":"1fe77f33a8b4aace957f49c4f21a293caf871b46ee62a4587e3edadb69838865"},
]

def dump(name,value): (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def fixture(fid,sid,box,approach=None): return {"id":fid,"semantic_id":sid,"footprint":box,"approach_zone":approach}

def audit_text():
 return """# ممیزی فقط‌خواندنی پیش از تغییر — لایه تجهیزات/پوشش/حرکت داخلی

منبع انتخاب‌شده: `ARCHITECTURAL_SYMBOL_LIBRARY_AND_PLAN_GRAPHICS_20260920_01`؛ checkpoint ترجیحی `SEMANTIC_GEOMETRY_CONSISTENCY_AND_PLAN_QA_20260920_01` هنگام شروع وجود نداشت. ممیزی پیش از هر تغییر انجام و snapshot زمان/حجم/SHA256 در `SOURCE_SNAPSHOTS.json` ثبت شد.

| FILE | CLASS-FUNCTION | CURRENT CAPABILITY | GAP | PROPOSED CHANGE | EXACT LOCATION | PROVENANCE | NON-REGRESSION DEPENDENCY |
|---|---|---|---|---|---|---|---|
| `architectural_symbol_library_v1.py` | `SYMBOL_LIBRARY` | نمادهای مبلمان و چند تجهیز تر | shower tray/zone، shaft و bidet قراردادی کامل نیست | نمادهای متمایز و mapping آینده DWG | `_RAW` و bundleهای BATH/WC | ابعاد `DESIGN_HEURISTIC` نه مقررات | primitive مشترک PDF/SVG حفظ شود |
| `furniture_placement_validator_v1.py` | `FurniturePlacementValidator.validate` | برخورد footprint با اتاق/در/پنجره/route | activity-zone و مسیر استفاده ریزدانه نیست | validator مستقل افزایشی؛ API قدیمی بدون تغییر | ماژول جدید `interior_fixture_finish_clearance_v1.py` | یادگیری انسانی HL-022 + requirement کاربر | failure codes قدیمی حفظ شوند |
| `architectural_scene_v1.py` | `ArchitecturalDrawingScene` | صحنه renderer-independent | قرارداد layer تجهیزات تر/finish/guide ناقص | primitiveهای vector موجود، بدون تغییر schema | مصرف از `add_review_graphics` | قرارداد صحنه موجود | extraction دیوار/بازشو guideها را نبیند |
| `architectural_realization_v1.py` | `LAYERS` | FIXTURES/FURNITURE دارد | FLOOR/WALL hatch و clearance guides ندارد | افزودن layer names، بدون تغییر مختصات candidate | ثابت `LAYERS` | requirement کاربر | wall/opening logic بدون تغییر |
| `svg_architectural_renderer_v1.py` | `_item/_symbol` | primitiveهای canonical برداری | hatch مستقل ندارد | `HATCH` به خطوط vector و role رنگی جدید | `_item`, color map | نمایش review؛ بدون ادعای مصالح اجرایی | SVG بدون raster بماند |
| `pdf_architectural_renderer_v1.py` | `_item/_symbol` | PDF بومی ReportLab | hatch مستقل ندارد | رسم مستقیم خطوط hatch | `_item`, color map | نمایش review | هیچ SVG→PDF ایجاد نشود |
| pipeline کاندیدها | `ArchitecturalPlanRealizer.realize` | چهار کاندید و consistency موجود | fixture-driven wet layout عمومی نشده | فعلاً synthetic capability proof؛ کاندیدها بازطراحی نشوند | runner و tests جدید | دستور صریح کاربر | coordinate patch ممنوع |
| ontology فعلی | wet rooms | wet/ventilation/furniture tags دارد | انتخاب ایرانی/فرنگی و composition قراردادی نیست | knowledge contract قابل override با program/user | JSON + kernel جدید | user/program/jurisdiction preference | انتخاب جهانی تحمیل نشود |
"""

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'READ_ONLY_AUDIT_FA.md').write_text(audit_text(),encoding='utf-8'); dump('SOURCE_SNAPSHOTS.json',ORIGINAL_SNAPSHOTS)
 c=contracts(); dump('INTERIOR_FIXTURE_KNOWLEDGE.json',c['fixtures']); dump('WET_SPACE_FINISH_CONTRACT.json',c['finishes'])
 dump('FURNITURE_CLEARANCE_CONTRACT.json',{"rules":c['clearance_rules'],"failure_codes":c['failure_codes'],"numeric_policy":"DESIGN_HEURISTIC_NOT_REGULATION"})
 dump('INTERIOR_USE_PATH_CONTRACT.json',c['interior_use_path'])
 ids=list(c['fixtures']); dump('FIXTURE_VECTOR_SYMBOL_LIBRARY.json',{sid:SYMBOL_LIBRARY[sid] for sid in ids if sid in SYMBOL_LIBRARY})

 room={"id":"SYNTH_BATH","type":"FAMILY_BATHROOM","polygon":[0,0,5,4],"ventilation_required":True}
 fixtures=[fixture("TUB","BATHTUB",[.2,.2,1.9,.95],[.2,.95,1.9,1.65]),fixture("BASIN","WASHBASIN",[2.2,.2,2.8,.7],[2.1,.7,2.9,1.4]),
   fixture("WC-I","WC_IRANIAN",[3.2,.2,3.8,1.0],[3.1,1,3.9,1.8]),fixture("DRAIN","FLOOR_DRAIN",[4.3,.2,4.45,.35]),fixture("SHAFT","WET_SHAFT",[4.5,.2,4.9,.6])]
 finishes=[{"id":"FLOOR-CERAMIC","type":"FLOOR_TILE_ZONE","extent":[0,0,5,4]}, {"id":"WALL-CERAMIC-S","type":"WALL_TILE_ZONE","extent":[0,0,5,.1],"host_wall_id":"SOUTH"}]
 wet=InteriorFixtureFinishValidator().validate(room,fixtures,finishes=finishes,room_walls=["SOUTH"]); dump('WET_SPACE_VALIDATION_RESULTS.json',wet)
 objects=[{"id":"BED","semantic_id":"DOUBLE_BED","footprint":[0,0,1.6,2],"activity_zone":[0,0,2.2,2.6]},
          {"id":"WARDROBE","semantic_id":"WARDROBE","footprint":[3,0,4.8,.6],"activity_zone":[3,.6,4.8,1.5]}]
 clear=FurnitureClearanceValidator().validate(objects,[{"id":"ROOM-ENTRY-TO-BED","critical":False,"segments":[[2.35,0,2.65,3.5]]}]); dump('CLEARANCE_VALIDATION_RESULTS.json',clear)
 scene=ArchitecturalDrawingScene('SYNTHETIC_WET_SPACE',metadata={"capability_layer_only":True,"candidate_coordinates_modified":False})
 scene.add('POLYGON','PARTITIONS',{'rect':{'x':0,'y':0,'w':5,'h':4}},{'fill':'none','stroke':'#222','line_width':.06})
 add_review_graphics(scene,fixtures,finishes,[{"id":f"APPROACH-{x['id']}","extent":x['approach_zone']} for x in fixtures if x.get('approach_zone')],
                     [{"id":"ENTRY-TO-FIXTURES","points":[[2.5,3.8],[2.5,2.0],[2.5,1.5]]}])
 dump('SYNTHETIC_WET_SPACE_DRAWING_SCENE.json',scene.to_dict())
 svg_renderer=SvgArchitecturalRenderer(px_per_m=92); svg_renderer.ox=300; svg_renderer.oy=760
 pdf_renderer=PdfArchitecturalRenderer(); pdf_renderer.s=92; pdf_renderer.ox=300; pdf_renderer.oy=650
 svg_renderer.render(scene,OUT/'SYNTHETIC_WET_SPACE_REVIEW.svg'); pdf_renderer.render(scene,OUT/'SYNTHETIC_WET_SPACE_REVIEW.pdf')
 cmd=[str(ROOT/'.venv'/'Scripts'/'python.exe'),'-m','pytest','-q','tests/architecture_generation/test_interior_fixture_finish_clearance_v1.py',
      'tests/architecture_generation/test_architectural_space_knowledge_v1.py','tests/architecture_generation/test_functional_architectural_design_gate_v1.py',
      'tests/architecture_generation/test_functional_architectural_design_gate_v2.py',f'--basetemp={ROOT / "tmp" / "pytest_interior_fixture_20260921_01"}']
 cp=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True); tests={"status":"PASS" if cp.returncode==0 else "FAIL","command":cmd,"stdout":cp.stdout,"stderr":cp.stderr,"returncode":cp.returncode}
 dump('TEST_RESULTS.json',tests)
 old_manifest=SOURCE/'FINAL_MANIFEST.json'; old_before=sha(old_manifest); historical_unchanged=old_before==sha(old_manifest)
 nonreg={"status":"PASS" if cp.returncode==0 and historical_unchanged else "FAIL","source_checkpoint":str(SOURCE),"source_manifest_sha256":old_before,
         "historical_checkpoints_modified":not historical_unchanged,"candidate_coordinates_modified":False,"native_pdf_scene_architecture_preserved":True,
         "svg_to_pdf_used":False,"minab_overlay_preserved":"NOT_TOUCHED","excluded":["STRUCTURE","BIM","IFC","H2","RENDER","IMAGE_GENERATION"]}
 dump('NON_REGRESSION_RESULTS.json',nonreg)
 acceptance=cp.returncode==0 and wet['status']=='PASS' and clear['status']=='PASS' and historical_unchanged
 manifest={"checkpoint":OUT.name,"created_at":datetime.now(timezone.utc).isoformat(),"source_checkpoint":SOURCE.name,
   "INTERIOR FIXTURE/FINISH SOFTWARE ACCEPTANCE":"PASS" if acceptance else "FAIL",
   "HUMAN ARCHITECTURAL ACCEPTANCE":"NOT APPLICABLE — CAPABILITY LAYER ONLY","wet_space_validation":wet['status'],"clearance_validation":clear['status'],
   "non_regression":nonreg['status'],"historical_checkpoints_modified":False,"numeric_policy":"HEURISTICS_ARE_NOT_REGULATIONS","artifacts":[]}
 for p in sorted(OUT.iterdir()):
  if p.is_file() and p.name!='FINAL_MANIFEST.json': manifest['artifacts'].append({"file":p.name,"bytes":p.stat().st_size,"sha256":sha(p)})
 dump('FINAL_MANIFEST.json',manifest)
 print(json.dumps({"output":str(OUT),"acceptance":manifest["INTERIOR FIXTURE/FINISH SOFTWARE ACCEPTANCE"],"tests":tests['status']},ensure_ascii=False,indent=2))
 return 0 if acceptance else 1

if __name__=='__main__': raise SystemExit(main())
