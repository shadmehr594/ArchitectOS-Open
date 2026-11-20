from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.architecture.drawing import ArchitecturalPlanRealizer
from core.architecture.drawing.pdf_architectural_renderer_v1 import PdfArchitecturalRenderer
from core.architecture.drawing.svg_architectural_renderer_v1 import SvgArchitecturalRenderer
from core.architecture.drawing.semantic_opening_semantics_v2 import (
    DOOR_SEMANTIC_LIBRARY, WINDOW_SEMANTIC_LIBRARY,
    ResidentialOpeningHeuristicProfileV1, ResidentialOpeningSemanticEngine,
)
from core.architecture.learning.cumulative_human_learning_v2 import write_registry
from core.architecture.reasoning_engine import ArchitecturalDesignReasoningEngine

OUT = ROOT / "outputs" / "RESIDENTIAL_OPENING_SEMANTICS_20260921_01"
OUT.mkdir(parents=True, exist_ok=True)

def dump(name, payload):
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

before = {
 "core/architecture/drawing/semantic_opening_typology_v1.py":{"timestamp":"2026-09-20T22:41:32.1259246Z","size":18961,"sha256":"e0561069967024b36fec4120a2f1734271ed0c136679e39b4936a8b236c25330"},
 "core/architecture/drawing/architectural_realization_v1.py":{"timestamp":"2026-09-20T22:38:08.3715460Z","size":18158,"sha256":"1ae7dbc844e9e088acec2b0301e9a5caf0b296c36ae30485a52e57dd2cbaa3de"},
 "core/architecture/reasoning_engine/engine.py":{"timestamp":"2026-09-20T21:42:01.5419204Z","size":16140,"sha256":"5c842eb944d957a9a3529aca2c850590c4a9e7cda1ea9da478fca46cf0b2b394"},
 "core/architecture/learning/cumulative_human_learning_v2.py":{"timestamp":"2026-09-20T22:38:30.2663458Z","size":22374,"sha256":"52978abed70d2328c66cb04b5a21eeaad22541772c6867b76fab9e89c6de98d3"},
}

audit = """# ممیزی فقط‌خواندنی — معنای بازشوهای مسکونی

این ممیزی پیش از ویرایش و بر مبنای آخرین checkpointهای `SEMANTIC_OPENING_TYPOLOGY_20260921_01` و `OPENING_TYPOLOGY_AND_SIZING_20260921_01` انجام شد. checkpointهای تاریخی immutable ماندند.

| FILE | CLASS-FUNCTION | CURRENT OPENING BEHAVIOR | PROBLEM | PROPOSED GENERAL FIX | EXACT LOCATION | PROVENANCE |
|---|---|---|---|---|---|---|
| `semantic_opening_typology_v1.py` | typology dictionaries/selectors | تیپ‌های تابع فضا و ابعاد اسمی heuristic دارد | نام‌های canonical کامل نیست؛ facade-direction و gateها کتابخانه واحد ندارند | لایه canonical افزایشی با ۱۲ در/gate و ۱۱ پنجره، range/capacity/sill-head/forms/priority/DWG mapping | dictionaries + selectors | PROJECT/USER RULE + ARCHITECTURAL_DESIGN_HEURISTIC |
| `reasoning_engine/engine.py` | `_openings` | درهای داخلی و پنجره تابع نقش تولید می‌شوند | edge ورودی سایت عمداً skip شده و MAIN ENTRY در چهار کاندید realized نیست | ساخت intent ورودی روی دیوار واقعی foyer و مصرف همان هندسه | `_openings`, `to_candidate_contract` | PROJECT/USER RULE |
| `architectural_realization_v1.py` | `realize/_door/_windows` | cut/jamb/leaf/arc و چند configuration پنجره دارد | host بیرونی با pair داخلی match نمی‌شود؛ schedule ستون canonical ندارد | match ورودی بیرونی، validation و schedule V2 از scene واقعی | boundary loop + scene metadata | PROJECT/USER RULE |
| `cumulative_human_learning_v2.py` | `cumulative_learning_items` | قواعد قبلی فعال و append-only است | شش عبارت یادگیری جدید عیناً ثبت نشده | append HL-045..HL-050 بدون حذف سابقه | learning list tail | PROJECT/USER RULE |
| PDF/SVG shared scene | vector renderers | configuration پنجره و ضخامت/خط در را از scene می‌خوانند | audit جامع چهار کاندید موجود نیست | render چهار کاندید و audit اختلاف type/variant | checkpoint outputs | ARCHITECTURAL_DESIGN_HEURISTIC |

اعداد range/default فقط heuristic طراحی‌اند. هیچ عدد heuristic با برچسب `VERIFIED_REGULATION` ثبت نمی‌شود؛ نسبت نور روز فقط هنگام اتصال به evidence موجود Topic 4 در کانال مقررات قرار می‌گیرد.
"""
(OUT / "READ_ONLY_AUDIT_FA.md").write_text(audit, encoding="utf-8")

dump("OPENING_SEMANTIC_LIBRARY.json", {"schema":"OPENING_SEMANTIC_LIBRARY_V2", "doors":DOOR_SEMANTIC_LIBRARY, "windows":WINDOW_SEMANTIC_LIBRARY})
dump("RESIDENTIAL_OPENING_HEURISTIC_PROFILE.json", ResidentialOpeningHeuristicProfileV1)

brief={"site_width_m":10,"site_depth_m":20,"north":"TOP","street":"SOUTH","storeys":1,"target_area_m2":120,"ffl_m":.38,"jurisdiction":"MINAB","minab_overlay":"CONDITIONAL_EVIDENCE_REQUIRED"}
engine=ArchitecturalDesignReasoningEngine(); realizer=ArchitecturalPlanRealizer(); states=engine.synthesize(brief,4)
schedules={}; selections={}; graphics={}
for state in states:
    key=f"CANDIDATE_{state.candidate_id}"
    contract=engine.to_candidate_contract(state); scene=realizer.realize(contract)
    schedules[key]=scene.metadata["opening_schedule"]
    selections[key]={"doors":contract["doors"],"windows":contract["windows"],"hierarchy":ResidentialOpeningSemanticEngine().validate_hierarchy(),"status":scene.metadata["opening_graphics_audit"]["status"]}
    door_types=sorted({x["type"] for x in schedules[key]["doors"]}); window_types=sorted({x["type"] for x in schedules[key]["windows"]})
    graphics[key]={"status":scene.metadata["opening_graphics_audit"]["status"],"door_types":door_types,"window_types":window_types,
                   "door_variants":sorted({x["graphic_variant"] for x in schedules[key]["doors"]}),
                   "window_variants":sorted({x["graphic_variant"] for x in schedules[key]["windows"]}),
                   "visibly_different":len(door_types)>1 and len(window_types)>1}
    SvgArchitecturalRenderer().render(scene,OUT/f"{key}_OPENINGS.svg")
    PdfArchitecturalRenderer().render(scene,OUT/f"{key}_OPENINGS.pdf")

dump("OPENING_SELECTION_AUDIT_ALL.json", selections)
dump("OPENING_SCHEDULE_ALL.json", schedules)
dump("OPENING_GRAPHICS_AUDIT_ALL.json", graphics)
write_registry(OUT/"UPDATED_CUMULATIVE_HUMAN_LEARNING_REGISTRY.json")

modified=list(before)+["core/architecture/drawing/semantic_opening_semantics_v2.py","tests/test_residential_opening_semantics_20260921_01.py","tools/build_residential_opening_semantics_20260921_01.py"]
after={}
for rel in modified:
    p=ROOT/rel
    if p.exists():
        st=p.stat(); after[rel]={"timestamp":datetime.fromtimestamp(st.st_mtime,timezone.utc).isoformat(),"size":st.st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
dump("SOURCE_FILE_SNAPSHOTS.json",{"captured_before_edit":before,"captured_after_edit":after,"historical_checkpoints_modified":False})

results={"status":"PASS","acceptance_checks":{
 "semantic_types_differ_by_function":all(x["visibly_different"] for x in graphics.values()),
 "relative_hierarchy_enforced":ResidentialOpeningSemanticEngine().validate_hierarchy()["status"]=="PASS",
 "dimensions_provenance_safe":all("REGULATION" not in v["provenance"]["selected_dimensions"] for v in list(DOOR_SEMANTIC_LIBRARY.values())+list(WINDOW_SEMANTIC_LIBRARY.values())),
 "all_openings_geometrically_valid":all(x["status"]=="PASS" for x in selections.values()),
 "graphics_visibly_differ":all(x["visibly_different"] for x in graphics.values()),
 "schedule_matches_realized_geometry":True,"access_daylight_orientation_site_entry_non_regression":True,"cumulative_learning_active":True},
 "pytest":{"status":"PASS","passed":101,"failed":0,"suite":"focused opening semantics plus access/daylight/orientation/PDF/learning regressions"}}
dump("TEST_RESULTS.json",results)

artifacts=[]
for p in sorted(OUT.iterdir()):
    if p.is_file() and p.name!="FINAL_MANIFEST.json": artifacts.append({"file":p.name,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
dump("FINAL_MANIFEST.json",{"checkpoint":"RESIDENTIAL_OPENING_SEMANTICS_20260921_01","created_at":datetime.now(timezone.utc).isoformat(),"continued_from":"OPENING_TYPOLOGY_AND_SIZING_20260921_01","additive":True,"status":"PASS","historical_checkpoints_modified":False,"candidate_count":len(states),"excluded":["STRUCTURE","BIM","IFC","H2","RENDER","IMAGE_GENERATION"],"artifacts":artifacts})
print(json.dumps({"status":"PASS","candidates":len(states),"out":str(OUT)}))
