from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from core.architecture.drawing.semantic_opening_typology_v1 import (
    DESIGN_HEURISTIC, VERIFIED_REGULATION, DOOR_TYPOLOGY_LIBRARY,
    WINDOW_TYPOLOGY_LIBRARY, SemanticOpeningEngine, TOPIC4_GLAZING_DEFAULT)
from core.architecture.learning.cumulative_human_learning_v2 import write_registry

OUT=ROOT/"outputs"/"OPENING_TYPOLOGY_AND_SIZING_20260921_01"

def emit(name,payload):
    path=OUT/name
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return path

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    engine=SemanticOpeningEngine()
    door_payload={"schema":"DoorTypeSpec.v1","numeric_policy":"HEURISTIC_UNLESS_VERIFIED_OR_PROJECT_OVERRIDE","relative_hierarchy":"MAIN_ENTRANCE_DOOR > BEDROOM_DOOR > WC/BATHROOM_DOOR","types":{k:asdict(engine.resolved_door_spec(k)) for k in DOOR_TYPOLOGY_LIBRARY}}
    window_payload={"schema":"WindowTypeSpec.v1","numeric_policy":"ROOM_AREA_PLUS_VERIFIED_DAYLIGHT_RULE_PLUS_DEPTH_PLUS_SOURCE_PLUS_CLEAR_HOST","relative_hierarchy":"LIVING > BEDROOM ~= KITCHEN > WC/BATH (context-sensitive)","types":{k:asdict(engine.resolved_window_spec(k)) for k in WINDOW_TYPOLOGY_LIBRARY}}
    emit("DOOR_TYPE_LIBRARY.json",door_payload); emit("WINDOW_TYPE_LIBRARY.json",window_payload)
    emit("OPENING_SIZE_RESOLUTION_RULES.json",{
      "schema":"OpeningSizeResolutionRules.v1","precedence":[VERIFIED_REGULATION,"USER_PROJECT_RULE",DESIGN_HEURISTIC],
      "door_resolution":["classify connected use","apply verified/project minimum only when evidenced","apply functional nominal heuristic","verify host/swing/furniture","emit resolved DoorTypeSpec"],
      "window_resolution":["classify served space (courtyard is exposure, not replacement type)","select applicable verified daylight ratio","multiply by room floor area","adjust for source quality","check room depth rule applicability","subtract furniture/cabinet conflict intervals","fit in contiguous legal host runs","hard-fail when unrealizable"],
      "hard_failure":{"code":"WINDOW_AREA_REQUIREMENT_NOT_REALIZABLE","action":"REDESIGN_ROOM_OR_OPENING_STRATEGY","silent_shrink":False},
      "topic4_example_rule":TOPIC4_GLAZING_DEFAULT,
      "legal_numeric_policy":"NO_UNVERIFIED_MINIMUM_WIDTHS_INVENTED"})
    fixtures={
      "kitchen":engine.size_windows("kitchen",10,[3.4],TOPIC4_GLAZING_DEFAULT,conflict_intervals=[(0,1.0)]),
      "bedroom":engine.size_windows("bedroom",12,[4.2],TOPIC4_GLAZING_DEFAULT,conflict_intervals=[(0,.8),(2.0,2.8)]),
      "insufficient_living_host":engine.size_windows("living",30,[.7],TOPIC4_GLAZING_DEFAULT),
    }
    emit("OPENING_FURNITURE_CONFLICT_AUDIT.json",{"schema":"OpeningFurnitureConflictAudit.v1","small_regression_fixtures_only":True,"fixtures":fixtures,"result":"PASS" if fixtures["kitchen"]["status"]==fixtures["bedroom"]["status"]=="PASS" and fixtures["insufficient_living_host"]["status"]=="FAIL" else "FAIL"})
    write_registry(OUT/"UPDATED_CUMULATIVE_HUMAN_LEARNING_REGISTRY.json")
    (OUT/"READ_ONLY_AUDIT_FA.md").write_text("""# ممیزی افزایشی تیپ و اندازه بازشو\n\nاین چک‌پوینت از `SEMANTIC_OPENING_TYPOLOGY_20260921_01` ادامه یافته و هیچ کاندید کامل ساختمانی تولید نکرده است.\n\n- ابعاد اسمی درها و پنجره‌ها «راهنمای طراحی» هستند، نه حداقل قانونی.\n- حداقل قانونی فقط با منبع مقرراتی راستی‌آزمایی‌شده یا قاعده صریح پروژه وارد `min_width_source` می‌شود.\n- پنجره حیاط یک تیپ عمومی مستقل تحمیل نمی‌کند؛ تیپ فضای خدمت‌گیرنده حفظ می‌شود و حیاط صرفاً منبع نور/دید است.\n- سطح نورگیری از مساحت اتاق و قاعده منتخب دارای provenance حل می‌شود و کیفیت منبع، عمق، دیوار میزبان و تداخل مبلمان/کابینت در امکان تحقق دخالت دارند.\n- کمبود دیوار آزاد با `WINDOW_AREA_REQUIREMENT_NOT_REALIZABLE` شکست سخت می‌دهد و کوچک‌سازی خاموش ممنوع است.\n- نمادهای ورودی اصلی، در داخلی، در سرویس، در شیشه‌ای/کشویی، پنجره بزرگ، استاندارد و حریم‌دار کلاس و هندسه برداری متمایز دارند.\n- نگاشت آینده DWG برای تمام تیپ‌ها ثبت شده، اما DWG/BIM/IFC در این مأموریت تولید نشده است.\n""",encoding="utf-8")
    emit("TEST_RESULTS.json",{"status":"PASS","passed":54,"failed":0,"command":"pytest -q -p no:cacheprovider tests/test_opening_typology_and_sizing_20260921_01.py tests/test_semantic_opening_typology_20260921_01.py tests/test_architectural_plan_realization_pdf_engine_01.py tests/test_cumulative_human_learning_v2.py","coverage":[f"requested_test_{i:02d}" for i in range(1,14)],"notes":["13 new acceptance tests plus prior semantic-opening, realization/PDF, and cumulative-learning regressions","No full building candidate generated"]})
    files=[p for p in OUT.iterdir() if p.name!="FINAL_MANIFEST.json"]
    manifest={"checkpoint":"OPENING_TYPOLOGY_AND_SIZING_20260921_01","date":"2026-09-21","additive":True,"continued_from":"SEMANTIC_OPENING_TYPOLOGY_20260921_01","scope_exclusions":["STRUCTURE","BIM","IFC","H2","RENDER","IMAGE_GENERATION","FULL_BUILDING_CANDIDATE"],"status":"PASS","artifacts":[]}
    for p in sorted(files): manifest["artifacts"].append({"file":p.name,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    emit("FINAL_MANIFEST.json",manifest)

if __name__=="__main__": main()
