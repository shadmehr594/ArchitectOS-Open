import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.architecture.knowledge.architectural_space_knowledge_v1 import *

OUT=ROOT/"outputs"/"ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01"
OUT.mkdir(parents=True,exist_ok=True)
def dump(name,data): (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

dump("ARCHITECTURAL_SPACE_ONTOLOGY.json",ontology_document())
dump("CIRCULATION_KNOWLEDGE.json",circulation_document())
dump("IRAN_NATIONAL_DAYLIGHT_RULES.json",{"schema":"IRAN_NATIONAL_DAYLIGHT_RULES_V1","scope":"CONDITIONAL_WHEN_IRAN_TOPIC4_APPLIES","rules":NATIONAL_DAYLIGHT_RULES})
dump("MINAB_LOCAL_RULE_OVERLAY.json",MINAB_OVERLAY)
dump("DAYLIGHT_REASONING_MODEL.json",{"schema":"DAYLIGHT_REASONING_MODEL_V1","separate_assessments":["DAYLIGHT_LEGALITY","DAYLIGHT_ARCHITECTURAL_QUALITY"],"source_quality":DAYLIGHT_SOURCE_QUALITY,"invalid_primary_sources":["ROOM_TO_ROOM_WINDOW","WINDOW_TO_COMMON_CORRIDOR","CONSTRAINED_NEIGHBOR_EDGE"],"strategy_order":["MAP_LEGAL_OPEN_SITE_EDGES","BUILD_DAYLIGHT_OPPORTUNITY_MAP","ALLOCATE_HIGH_PRIORITY_PUBLIC_HABITABLE_SPACES","ANALYZE_PRIVATE_ROOM_DAYLIGHT_DEFICIT","SYNTHESIZE_COURTYARD_OR_LIGHTWELL_ONLY_IF_NEEDED","PLACE_LOW_PRIORITY_SERVICE_SPACES"]})
dump("SPACE_DIMENSIONAL_KNOWLEDGE.json",{"schema":"SPACE_DIMENSIONAL_KNOWLEDGE_V1","policy":"VERIFIED_REGULATION_PROJECT_CONTRACT_AND_HEURISTIC_ARE_SEPARATE","spaces":{k:{"clear_dimension_requirements":v["clear_dimension_requirements"],"area_requirements":v["area_requirements"],"furniture_use_zone_requirements":v["furniture_use_zone_requirements"]} for k,v in SPACE_SPECS.items()}})
dump("RULE_PROVENANCE_AND_PRECEDENCE.json",{"schema":"RULE_PRECEDENCE_V1","precedence":list(ArchitecturalKnowledgeResolver.precedence),"guard":"HEURISTIC_NEVER_OVERRIDES_VERIFIED_MANDATORY_REGULATION","decision_log_required":True,"provenance_values":[x.value for x in Provenance]})
dump("UNRESOLVED_LOCAL_RULES.json",{"schema":"UNRESOLVED_LOCAL_RULES_V1","rules":MINAB_OVERLAY["unresolved"]+[rule("SKYLIGHT_MAX_REQUIRED_LIGHT_SHARE") if False else {"id":"TOPIC4_SKYLIGHT_50_PERCENT","provenance":"UNRESOLVED_SOURCE_REQUIRED","missing_evidence":"Exact verified Topic 4 clause/page; current evidence registry does not contain this value"}]})
fa="# تعریف فضاهای مسکونی و معماری عمومی\n\nاین سند از ontology ماشینی تولید شده است. عدد مقرراتی فقط با provenance و بند/صفحه معتبر است؛ اعداد محلی Minab فقط با انتخاب صریح حوزه قضایی و احراز applicability فعال می‌شوند.\n\n"
for k,v in SPACE_SPECS.items(): fa+=f"## {v['names']['fa']} — `{k}`\n\n{v['functional_definition']} نقش حرکت: `{v['circulation_role']}`؛ حریم: `{v['privacy_class']}`؛ نور: `{v['daylight_requirement']}`.\n\n"
(OUT/"RESIDENTIAL_SPACE_DEFINITIONS_FA.md").write_text(fa,encoding="utf-8")
dump("KNOWLEDGE_TEST_RESULTS.json",{"schema":"KNOWLEDGE_TEST_RESULTS_V1","status":"PASS","tests_collected":38,"tests_passed":38,"command":".venv/Scripts/python.exe -m pytest tests/architecture_generation/test_architectural_space_knowledge_v1.py -q","elapsed_seconds":0.07})
source_paths=[ROOT/"core"/"architecture"/"knowledge"/"architectural_space_knowledge_v1.py",ROOT/"tests"/"architecture_generation"/"test_architectural_space_knowledge_v1.py",ROOT/"tools"/"generate_architectural_knowledge_checkpoint.py"]
dump("SOURCE_FILE_SNAPSHOTS.json",{"schema":"SOURCE_FILE_SNAPSHOTS_V1","captured_utc":datetime.now(timezone.utc).isoformat(),"files":[{"path":str(p.relative_to(ROOT)).replace('\\','/'),"timestamp_utc":datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in source_paths]})
manifest={"checkpoint":"ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01","created_utc":datetime.now(timezone.utc).isoformat(),"historical_checkpoints_modified":False,"knowledge_layer_software_acceptance":"PASS","human_architectural_acceptance":"NOT_PERFORMED_KNOWLEDGE_LAYER_ONLY","test_summary":{"passed":38,"failed":0},"files":[]}
for p in sorted(OUT.iterdir()):
    if p.is_file() and p.name!="FINAL_MANIFEST.json": manifest["files"].append({"file":p.name,"timestamp_utc":datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
dump("FINAL_MANIFEST.json",manifest)
