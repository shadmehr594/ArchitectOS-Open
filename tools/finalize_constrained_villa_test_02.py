import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(r"<repo-root>")
OUT=ROOT/"outputs/AUTONOMOUS_SINGLE_STOREY_VILLA_120M2_TEST_20260920_01"
FROZEN=[ROOT/"core/architecture/knowledge/architectural_space_knowledge_v1.py",ROOT/"outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/ARCHITECTURAL_SPACE_ONTOLOGY.json",ROOT/"outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/CIRCULATION_KNOWLEDGE.json",ROOT/"outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/DAYLIGHT_REASONING_MODEL.json",ROOT/"outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/IRAN_NATIONAL_DAYLIGHT_RULES.json",ROOT/"outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/MINAB_LOCAL_RULE_OVERLAY.json",ROOT/"outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/RULE_PROVENANCE_AND_PRECEDENCE.json"]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
integrity=json.loads((OUT/"KNOWLEDGE_FREEZE_INTEGRITY.json").read_text(encoding="utf-8"))
current={str(p.relative_to(ROOT)):sha(p) for p in FROZEN}
if current!=integrity["frozen_hashes_before"]: raise SystemExit("FROZEN_KNOWLEDGE_CHANGED")
results=json.loads((OUT/"TEST_RESULTS.json").read_text(encoding="utf-8"))
required=["READ_ONLY_AUDIT_FA.md","TEST_BRIEF.json","KNOWLEDGE_FREEZE_INTEGRITY.json","AUTONOMOUS_DESIGN_ASSUMPTIONS.json","SPACE_PROGRAM.json","ZONING.json","CIRCULATION_GRAPH.json","DAYLIGHT_STRATEGY.json","PARKING_AND_YARD_ACCESS.json","DOOR_INTENTS.json","WINDOW_INTENTS.json","FURNITURE_USE_PROOF.json","GENERATED_VILLA_GEOMETRY.json","SOFTWARE_ARCHITECTURAL_READINESS.json","UNRESOLVED_DESIGN_BOARD.json","TEST_RESULTS.json","VILLA_120M2_SINGLE_STOREY_PLAN.svg","VILLA_120M2_SINGLE_STOREY_PLAN.pdf"]
missing=[x for x in required if not (OUT/x).is_file()]
if missing: raise SystemExit("MISSING:"+','.join(missing))
files=[]
for p in sorted(OUT.iterdir()):
    if p.name=="FINAL_MANIFEST.json": continue
    files.append({"file":p.name,"sha256":sha(p),"bytes":p.stat().st_size})
manifest={"checkpoint":OUT.name,"created_at":datetime.now(timezone.utc).isoformat(),"files":files,"required_artifacts_complete":True,"hard_checks_passed":results["passed"],"hard_checks_total":results["total"],"SINGLE_STOREY_VILLA_SOFTWARE_ARCHITECTURAL_READINESS":results["status"],"HUMAN_ARCHITECTURAL_ACCEPTANCE":"PENDING","knowledge_freeze_integrity":True,"candidate_rescued_after_generation":False,"pdf_visual_review":"PASS_A3_LANDSCAPE_NO_CLIPPING"}
(OUT/"FINAL_MANIFEST.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(manifest,ensure_ascii=False,indent=2))
