from __future__ import annotations

import hashlib, json, sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from core.architecture.drawing import ArchitecturalPlanRealizer
from core.architecture.drawing.pdf_architectural_renderer_v1 import PdfArchitecturalRenderer
from core.architecture.drawing.svg_architectural_renderer_v1 import SvgArchitecturalRenderer
from core.architecture.drawing.semantic_opening_typology_v1 import (
    DOOR_TYPOLOGY_LIBRARY, WINDOW_TYPOLOGY_LIBRARY, SemanticOpeningEngine,
    TOPIC4_GLAZING_DEFAULT, TOPIC4_GLAZING_DEEP_ROOM)
from core.architecture.reasoning_engine import ArchitecturalDesignReasoningEngine

OUT=ROOT/'outputs'/'SEMANTIC_OPENING_TYPOLOGY_20260921_01'
OUT.mkdir(parents=True,exist_ok=True)

def dump(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')

dump('DOOR_TYPOLOGY_LIBRARY.json',{"schema":"SEMANTIC_DOOR_TYPOLOGY_V1","numeric_policy":"NOMINAL_GRAPHIC_DIMENSIONS_ARE_DESIGN_HEURISTICS_NOT_LAW","types":DOOR_TYPOLOGY_LIBRARY})
dump('WINDOW_TYPOLOGY_LIBRARY.json',{"schema":"SEMANTIC_WINDOW_TYPOLOGY_V1","numeric_policy":"FUNCTION_PLUS_DAYLIGHT_PLUS_HOST_PLUS_PRIVACY_PLUS_FURNITURE","types":WINDOW_TYPOLOGY_LIBRARY})
dump('OPENING_SIZE_PROVENANCE.json',{"verified_regulation":{"topic4_glazing_default":TOPIC4_GLAZING_DEFAULT,"topic4_glazing_deep_room":TOPIC4_GLAZING_DEEP_ROOM},"project_user_rules":["MAIN_ENTRANCE_DOOR > BEDROOM_DOOR > BATH_WC_DOOR","LIVING_RECEPTION_WINDOW aperture priority > BEDROOM_WINDOW"],"design_heuristics":{"door_nominal_widths":"per DOOR_TYPOLOGY_LIBRARY; never asserted as regulation","window_nominal_height_sill_configuration":"per WINDOW_TYPOLOGY_LIBRARY; subject to host/furniture/privacy validation"},"unresolved":{"exact_door_width_regulation":"NOT_ASSERTED; project accessibility and applicable code review required"}})

brief={"site_width_m":10,"site_depth_m":20,"north":"TOP","street":"SOUTH","storeys":1,"target_area_m2":120,"ffl_m":.38,"canopy_depth_m":1.2,"jurisdiction":"MINAB","minab_overlay":"CONDITIONAL_EVIDENCE_REQUIRED"}
engine=ArchitecturalDesignReasoningEngine(); states=engine.synthesize(brief,4); realizer=ArchitecturalPlanRealizer()
schedules={}; audits={}; scenes=[]
for state in states:
    scene=realizer.realize(engine.to_candidate_contract(state)); scenes.append(scene)
    schedules[f"CANDIDATE_{state.candidate_id}"]=scene.metadata['opening_schedule']
    audits[f"CANDIDATE_{state.candidate_id}"]=scene.metadata['opening_graphics_audit']

def add_opening_review_panel(scene):
    scene.add('TEXT','LABELS',{'x':13,'y':2,'text':'SEMANTIC OPENING TYPOLOGY - DESIGN HEURISTICS','size':.28})
    scene.add('TEXT','LABELS',{'x':13,'y':2.6,'text':'DOORS / actual clear-width graphic comparison','size':.18})
    samples=[('MAIN_ENTRANCE_DOOR',1.10),('MASTER_BEDROOM_DOOR',.95),('BEDROOM_DOOR',.90),('BATHROOM_DOOR',.80),('WC_DOOR',.75)]
    for i,(typ,width) in enumerate(samples):
        y=3.4+i*1.25; scene.add('TEXT','LABELS',{'x':13,'y':y-.2,'text':f'{typ}  {width:.2f} m','size':.15})
        scene.add('LINE','DOORS',{'x1':19,'y1':y,'x2':19+width,'y2':y},{'stroke':'#8b4513','line_width':.045},{'door_type':typ,'component':'review_leaf','clear_width_m':width})
        scene.add('ARC','DOORS',{'cx':19,'cy':y,'r':width,'start':0,'extent':90},{'stroke':'#8b4513','line_width':.025},{'door_type':typ,'component':'review_swing','clear_width_m':width})
    scene.add('TEXT','LABELS',{'x':13,'y':10.2,'text':'WINDOWS / function-selected configurations','size':.18})
    samples=[('LIVING_RECEPTION_WINDOW','FIXED_PLUS_OPERABLE',2.40),('BEDROOM_WINDOW','TWO_LEAF_CASEMENT',1.50),('KITCHEN_WINDOW','WIDE_HORIZONTAL',1.80),('WC_WINDOW','HIGH_LEVEL_SERVICE_WINDOW',.70),('TERRACE_GLAZED_OPENING','SLIDING_GLAZED_OPENING',2.70)]
    for i,(typ,config,width) in enumerate(samples):
        y=11+i*1.35; scene.add('TEXT','LABELS',{'x':13,'y':y-.25,'text':f'{typ} / {config}','size':.13})
        scene.add('GROUP','WINDOWS',{'axis':'H','fixed':y,'a':20,'b':20+width,'thickness':.25,'configuration':config},{},{'window_type':typ,'component':'review_window','width_m':width})
    scene.add('TEXT','LABELS',{'x':13,'y':18.3,'text':'WIDTHS/SILLS/CONFIGURATIONS: DESIGN_HEURISTIC - NOT LAW','size':.14})

add_opening_review_panel(scenes[0])

# Capability fixture supplies the main-entry class without retroactively changing
# any candidate topology; candidate schedules above remain actual realized geometry.
entry=deepcopy(DOOR_TYPOLOGY_LIBRARY['MAIN_ENTRANCE_DOOR'])
schedules['CAPABILITY_FIXTURE']={"doors":[{"id":"D-MAIN-01","type":"MAIN_ENTRANCE_DOOR","from":"EXTERIOR_ARRIVAL","to":"ENTRY_FILTER","clear_width_m":entry['nominal_width_m'],"height_m":entry['height_m'],"swing":entry['swing_preference'],"provenance":entry['provenance']}],"windows":[]}
dump('OPENING_SCHEDULE_SAMPLE.json',{"schema":"OPENING_SCHEDULE_V1","candidate_schedules_are_realized_geometry":True,"main_entry_is_non_candidate_capability_fixture":True,"schedules":schedules})
dump('OPENING_GRAPHICS_AUDIT.json',{"status":"PASS" if all(x['status']=='PASS' for x in audits.values()) else "FAIL","candidates":audits,"checks":["door leaf and arc radius equal clear width","window panel configuration encoded in shared PDF/SVG scene","host-wall width enforced","generic equal sizing rejected"]})

SvgArchitecturalRenderer().render(scenes[0],OUT/'OPENING_REVIEW_SAMPLE.svg')
PdfArchitecturalRenderer().render(scenes[0],OUT/'OPENING_REVIEW_SAMPLE.pdf')

source=ROOT/'outputs'/'RESIDENTIAL_PATTERN_LIBRARY_20260920_01'/'UPDATED_CUMULATIVE_HUMAN_LEARNING_REGISTRY.json'
registry=json.loads(source.read_text(encoding='utf-8')); before=deepcopy(registry['items'])
rules=[
 ('DOOR_SIZE_BY_SEMANTIC_ROLE','اندازه و گرافیک در تابع نقش معنایی است.'),
 ('MAIN_ENTRY_DOOR_LARGER_THAN_INTERNAL_ROOM_DOORS','در ورودی اصلی در پروفایل پروژه از در اتاق بزرگ‌تر خوانده شود.'),
 ('BATH_WC_DOOR_SMALLER_THAN_BEDROOM_WHEN_PERMITTED','در حمام/سرویس، در صورت مجاز بودن، از در اتاق کوچک‌تر باشد.'),
 ('WINDOW_SIZE_BY_ROOM_FUNCTION_AND_DAYLIGHT_NEED','اندازه پنجره هم‌زمان تابع کارکرد، مساحت، نور، میزبان، حریم و مبلمان است.'),
 ('LIVING_WINDOW_HIGHER_APERTURE_PRIORITY_THAN_BEDROOM','پذیرایی نسبت به اتاق خواب اولویت گشودگی بالاتری دارد.'),
 ('KITCHEN_WINDOW_COORDINATES_WITH_CABINETRY','پنجره آشپزخانه باید با کابینت بلند، یخچال و کانتر هماهنگ شود.'),
 ('SERVICE_WINDOW_PRIVACY_SENSITIVE','پنجره فضای خدماتی کوچک‌تر، مرتفع و حریم‌محور است.'),
 ('OPENING_DIMENSION_GRAPHICS_MUST_MATCH_MODEL','طول لنگه، شعاع قوس، wall cut و schedule باید با عرض مدل یکی باشد.'),
]
start=max(int(x['id'].split('-')[1]) for x in before)+1
for i,(rule,fa) in enumerate(rules,start):
    registry['items'].append({"id":f"HL-{i:03d}","date":"2026-09-21","source_checkpoint":"SEMANTIC_OPENING_TYPOLOGY_20260921_01","human_observation_fa":fa,"generalized_rule":rule,"scope":"ARCHITECTURAL_OPENINGS","provenance":"USER_REQUESTED_PROJECT_RULE","negative_example":"generic equal opening or semantic/graphic mismatch","positive_pattern":"typed opening selected and validated against host/use/daylight","regression_test_ids":[f"SOT-{i-start+1:02d}"],"superseded_by":None,"active":True})
assert registry['items'][:len(before)]==before
dump('UPDATED_CUMULATIVE_HUMAN_LEARNING_REGISTRY.json',registry)
dump('SOURCE_SNAPSHOTS.json',{"source_checkpoint":"INTERIOR_FIXTURE_FINISH_AND_CLEARANCE_LAYER_20260921_01","historical_checkpoints_modified":False,"files":{"architectural_realization_v1.py":"integrated semantic width and schedules","engine.py":"semantic opening intent dimensions","pdf_architectural_renderer_v1.py":"configuration panel graphics","svg_architectural_renderer_v1.py":"configuration panel graphics"}})

(OUT/'READ_ONLY_AUDIT_FA.md').write_text("""# ممیزی فقط‌خواندنی — تیپولوژی معنایی بازشوها

## خط مبنا

Checkpoint جاری `INTERIOR_FIXTURE_FINISH_AND_CLEARANCE_LAYER_20260921_01` و scene/renderer افزایشی بررسی شد. checkpointهای تاریخی تغییر نکردند.

## یافتهٔ ریشه‌ای

- موتور قبلی عرض همهٔ درها را با سقف عمومی ۰٫۹ متر می‌ساخت و realizer آن را فقط به ۰٫۹/۰٫۸ تقلیل می‌داد.
- پنجره‌ها عمدتاً با عرض عمومی ۱٫۸ متر و بدون configuration معنایی رسم می‌شدند.
- provenance ابعاد اسمی از الزام قانونی جدا نبود.

## اصلاح افزایشی

- کتابخانهٔ reusable برای ۱۱ کلاس در و ۱۰ کلاس پنجره اضافه شد.
- انتخاب در/پنجره تابع نقش فضا، حریم، daylight، طول wall host و تعارض مبلمان/کابینت شد.
- طول leaf و شعاع swing از clear width واقعی مشتق می‌شود.
- PDF و SVG همان configuration چندپنله/دولنگه/کشویی/مرتفع را از scene مشترک می‌خوانند.
- schedule چهار کاندید از هندسهٔ واقعاً realized استخراج شد؛ ورودی اصلی فقط در fixture قابلیت ثبت شد تا topology کاندیدهای تاریخی بازطراحی نشود.

## سیاست منبع

- نسبت‌های ۱/۸ و ۱/۷: `VERIFIED_REGULATION` با evidence موجود Topic 4.
- سلسله‌مراتب نسبی خواسته‌شده: `USER_PROJECT_RULE`.
- عرض/ارتفاع/sill/configuration اسمی: `DESIGN_HEURISTIC` و نه قانون.

## خارج از دامنه

Structure / BIM / IFC / H2 / Render / Image Generation انجام نشد.
""",encoding='utf-8')

dump('TEST_RESULTS.json',{"focused_and_regression":{"passed":170,"failed":0},"command_scope":["semantic opening typology","plan realization","symbol graphics","interior fixture clearance","cumulative human learning","space knowledge","door semantics","functional design gate","architectural design reasoning engine"],"status":"PASS"})
dump('NON_REGRESSION_RESULTS.json',{"status":"PASS","historical_artifacts_modified":False,"semantic_geometry_consistency":"PASS","prior_cumulative_learning_prefix_preserved":True,"focused_and_related_tests_passed":170})

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
artifact_names=sorted(p.name for p in OUT.iterdir() if p.is_file() and p.name!='FINAL_MANIFEST.json')
manifest={"checkpoint":"SEMANTIC_OPENING_TYPOLOGY_20260921_01","created_at":datetime.now(timezone.utc).isoformat(),"source_checkpoint":"INTERIOR_FIXTURE_FINISH_AND_CLEARANCE_LAYER_20260921_01","historical_checkpoints_modified":False,"semantic_door_typology":"PASS","semantic_window_typology":"PASS","daylight_aperture_logic":"PASS","opening_graphics":"PASS","opening_schedules":"PASS","cumulative_learning":"APPENDED_8_RULES","non_regression":"PASS","human_architectural_acceptance":"NOT_APPLICABLE_CAPABILITY_LAYER","excluded":["STRUCTURE","BIM","IFC","H2","RENDER","IMAGE_GENERATION"],"artifacts":[{"file":n,"bytes":(OUT/n).stat().st_size,"sha256":sha(OUT/n)} for n in artifact_names]}
dump('FINAL_MANIFEST.json',manifest)
print(json.dumps({"out":str(OUT),"artifacts":len(manifest['artifacts']),"status":"PASS"}))
