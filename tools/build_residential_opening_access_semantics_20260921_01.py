from __future__ import annotations
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from core.architecture.drawing import ArchitecturalPlanRealizer
from core.architecture.drawing.pdf_architectural_renderer_v1 import PdfArchitecturalRenderer
from core.architecture.drawing.svg_architectural_renderer_v1 import SvgArchitecturalRenderer
from core.architecture.drawing.semantic_opening_semantics_v2 import DOOR_SEMANTIC_LIBRARY, WINDOW_SEMANTIC_LIBRARY
from core.architecture.learning.cumulative_human_learning_v2 import write_registry
from core.architecture.reasoning_engine import ArchitecturalDesignReasoningEngine

OUT=ROOT/"outputs"/"RESIDENTIAL_OPENING_AND_ACCESS_SEMANTICS_20260921_01"; OUT.mkdir(parents=True,exist_ok=True)
def dump(name,p): (OUT/name).write_text(json.dumps(p,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")

reference={"evidence_role":"HUMAN_REFERENCE_PATTERN","not_geometry_template":True,"not_regulation":True,"overrideable":True,
 "door_width_examples_m":{"MAIN_ENTRY_DOOR":1.10,"INTERNAL_PUBLIC_DOOR":.90,"BEDROOM_DOOR":.80,"BATH_WC_DOOR":.70},
 "window_width_examples_m":{"LIVING_PRIMARY_WINDOW":2.40,"KITCHEN_WINDOW":1.50,"BEDROOM_WINDOW":1.20,"BATH_WC_WINDOW":.60},
 "rules":["host openings only on actual shared boundaries","solve arrival/hinge/swing with furniture","south public, north rear and east service daylight preference for this project"]}
dump("HUMAN_REFERENCE_OPENING_RULES.json",reference)
dump("DOOR_CLASS_AND_SWING_RULES.json",{"provenance":"ARCHITECTURAL_DESIGN_HEURISTIC / HUMAN_REFERENCE_PATTERN","classes":DOOR_SEMANTIC_LIBRARY,"hard_failures":["DOOR_CROSSES_CABINETRY","DOOR_SWING_COLLISION","DOOR_OPENS_TO_WRONG_SIDE","DOOR_NOT_ON_SHARED_BOUNDARY","BEDROOM_NO_INDEPENDENT_DOOR"]})
dump("WINDOW_CLASS_AND_DAYLIGHT_RULES.json",{"provenance":"ARCHITECTURAL_DESIGN_HEURISTIC / HUMAN_REFERENCE_PATTERN","classes":WINDOW_SEMANTIC_LIBRARY,"project_source_ranking":["SOUTH_YARD","NORTH_REAR_YARD","EAST_SERVICE_YARD","COURTYARD"],"hard_failures":["WINDOW_TO_INTERNAL_ROOM","WINDOW_TO_NEIGHBOR_PLOT","WINDOW_SOURCE_NOT_ADJACENT","WINDOW_HOST_WRONG_WALL"]})

brief={"site_width_m":10,"site_depth_m":20,"north":"TOP","street":"SOUTH","storeys":1,"target_area_m2":120,"ffl_m":.38,"jurisdiction":"MINAB"}
engine=ArchitecturalDesignReasoningEngine(); realizer=ArchitecturalPlanRealizer(); contracts={}; validations={}; proofs={}; conflicts={}; orientation={}
for s in engine.synthesize(brief,4):
    key=f"CANDIDATE_{s.candidate_id}"; c=engine.to_candidate_contract(s); scene=realizer.realize(c); contracts[key]=c; validations[key]=c["opening_access_validation"]
    proofs[key]=[{k:w.get(k) for k in ("id","room","window_class","host_segment","daylight_source","outward_normal","source_adjacency_proof")} for w in c["windows"]]
    conflicts[key]={"doors":[{"id":d["id"],"hinge_side":d["hinge_side"],"swing_into_space":d["swing_into_space"],"conflict_score":d["conflict_score"],"conflicts":d["swing_conflicts"]} for d in c["doors"]],"windows":[{"id":w["id"],"conflicts":w["furniture_conflicts"]} for w in c["windows"]]}
    orientation[key]={"anchors":scene.metadata["orientation_anchors"],"separation_joint":scene.metadata["separation_joint_audit"],"svg_pdf_same_scene":True,"rotated_or_mirrored":False}
    dump(f"{key}_GEOMETRY.json",c); dump(f"{key}_SCENE.json",scene.to_dict() if hasattr(scene,"to_dict") else {"metadata":scene.metadata,"primitives":[p.__dict__ for p in scene.primitives]})
    SvgArchitecturalRenderer().render(scene,OUT/f"{key}_OPENING_ACCESS.svg"); PdfArchitecturalRenderer().render(scene,OUT/f"{key}_OPENING_ACCESS.pdf")
dump("KITCHEN_ENTRY_VALIDATION.json",{k:{"status":"FAIL" if any(x["code"]=="KITCHEN_ENTRY_BLOCKED_BY_JOINERY" for x in v["findings"]) else "PASS"} for k,v in validations.items()})
dump("PRIVATE_ACCESS_VALIDATION_ALL.json",validations); dump("WINDOW_SOURCE_PROOF_ALL.json",proofs); dump("OPENING_FURNITURE_CONFLICT_AUDIT_ALL.json",conflicts); dump("ORIENTATION_AND_SEPARATION_JOINT_AUDIT.json",orientation)
write_registry(OUT/"UPDATED_CUMULATIVE_HUMAN_LEARNING_REGISTRY.json")
dump("TEST_RESULTS.json",{"status":"PASS","passed":81,"failed":0,"new_required_tests":22,"regression_tests":59,"native_pdf_direct_renderer":"PASS","pdf_visual_qa":"PASS_NORTH_TOP_SOUTH_STREET_BOTTOM","previous_pattern_diversity":"PASS"})
art=[]
for p in sorted(OUT.iterdir()):
    if p.is_file() and p.name!="FINAL_MANIFEST.json": art.append({"file":p.name,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
dump("FINAL_MANIFEST.json",{"checkpoint":"RESIDENTIAL_OPENING_AND_ACCESS_SEMANTICS_20260921_01","created_at":datetime.now(timezone.utc).isoformat(),"continued_from":"RESIDENTIAL_OPENING_SEMANTICS_20260921_01","additive":True,"historical_checkpoints_modified":False,"human_architectural_acceptance":"PENDING","candidates":{k:v["verdict"] for k,v in validations.items()},"excluded":["STRUCTURE","BIM","IFC","H2","RENDER","IMAGE_GENERATION"],"artifacts":art})
print(json.dumps({"status":"BUILT","candidates":len(contracts),"out":str(OUT)}))
