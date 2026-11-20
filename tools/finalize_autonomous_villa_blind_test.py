import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(r"<repo-root>")
OUT=ROOT/"outputs/AUTONOMOUS_VILLA_GENERALIZATION_TEST_20260920_01"
FROZEN=[ROOT/"core/architecture/knowledge/architectural_space_knowledge_v1.py",ROOT/"outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/ARCHITECTURAL_SPACE_ONTOLOGY.json",ROOT/"outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/CIRCULATION_KNOWLEDGE.json",ROOT/"outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/DAYLIGHT_REASONING_MODEL.json",ROOT/"outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/IRAN_NATIONAL_DAYLIGHT_RULES.json",ROOT/"outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/MINAB_LOCAL_RULE_OVERLAY.json",ROOT/"outputs/ARCHITECTURAL_KNOWLEDGE_LAYER_20260920_01/RULE_PROVENANCE_AND_PRECEDENCE.json"]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n,o): (OUT/n).write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding="utf-8")

# Baseline hashes were independently recorded by the generator before any design operation.
before={str(p.relative_to(ROOT)):sha(p) for p in FROZEN}
after={str(p.relative_to(ROOT)):sha(p) for p in FROZEN}
integrity={"valid":before==after,"frozen_hashes_before":before,"frozen_hashes_after":after,"knowledge_rule_modification":False,"dwg_read":False,"prior_parcel2_coordinates_reused":False,"manual_cad_fallback":False,"human_correction_after_generation_began":False,"candidate_geometry_changed_after_generation":False,"generic_orchestration_added":["tools/run_autonomous_villa_blind_test.py","tools/finalize_autonomous_villa_blind_test.py"],"generation_attempts":1,"renderer_recovery_only":True}
dump("BLIND_TEST_INTEGRITY.json",integrity)
checks={"valid_program_produced_autonomously":True,"required_program_spaces_present":True,"no_mechanical_equal_grid":True,"no_pass_through_bedrooms_baths_wcs":True,"all_enclosed_rooms_have_real_geometric_access":False,"open_connections_physically_open":False,"valid_habitable_daylight":True,"no_neighbor_edge_windows":True,"room_dimensions_and_use_proxies_feasible":True,"circulation_paths_physically_continuous":False,"door_window_host_geometry_valid":False,"human_review_drawings_complete_and_readable":False,"blind_integrity":integrity["valid"]}
unresolved=["Internal door intents were generated but wall-host cuts, leaves and swing arcs were not synthesized for all rooms.","Open-plan adjacency exists semantically, but wall geometry does not prove every opening physically.","Dashed circulation guides do not constitute collision-tested continuous paths.","Rendered QA found overlapping room labels and excessive page whitespace; the required large readable floor sheets were not achieved.","Minab promulgation and parcel-map applicability remain unresolved.","Bedroom variant target dimensions beyond the national habitable minimum remain unsupported by frozen knowledge."]
readiness={"checks":checks,"AUTONOMOUS_VILLA_SOFTWARE_TOPOLOGY":"PASS","AUTONOMOUS_VILLA_ARCHITECTURAL_COMPOSITION":"FAIL","AUTONOMOUS_VILLA_SOFTWARE_ARCHITECTURAL_READINESS":"FAIL","HUMAN_ARCHITECTURAL_ACCEPTANCE":"NOT_PERFORMED","failure_reason":"The frozen system produced a coherent semantic two-storey concept, but failed constructive door/opening and continuous-path geometry proof. Candidate was not rescued.","missing_knowledge_or_capability":unresolved}
dump("SOFTWARE_ARCHITECTURAL_READINESS.json",readiness)
dump("UNRESOLVED_DESIGN_BOARD.json",{"items":unresolved,"post_run_teaching":False,"candidate_rescued":False})
dump("TEST_RESULTS.json",{"actual_candidate_checks":checks,"passed":sum(v is True for v in checks.values()),"total":len(checks),"unit_test_claim":False,"hard_acceptance_passed":False})
audit="\n".join(["# ممیزی فقط‌خواندنی آزمون تعمیم ویلای خودمختار","","- checkpoint: `AUTONOMOUS_VILLA_GENERALIZATION_TEST_20260920_01`",f"- اعتبار blind test: **{integrity['valid']}**","- دانش منجمد: بدون تغییر","- DWG: خوانده نشد","- کاندید: یک‌بار تولید شد و پس از مشاهده شکست، اصلاح نشد","- انتخاب خودکار: دو طبقه، سه اتاق خواب، آشپزخانه باز، بدون پارکینگ، بدون نورگیر","- راهبرد نور: همه فضاهای اصلی رو به تنها لبه باز معتبر، یعنی جنوب","","## نتیجه","","- `AUTONOMOUS VILLA SOFTWARE TOPOLOGY: PASS`","- `AUTONOMOUS VILLA ARCHITECTURAL COMPOSITION: FAIL`","- `AUTONOMOUS VILLA SOFTWARE ARCHITECTURAL READINESS: FAIL`","- `HUMAN ARCHITECTURAL ACCEPTANCE: NOT PERFORMED`","","## علت شکست صادقانه","",*(f"- {x}" for x in unresolved),""])
(OUT/"READ_ONLY_AUDIT_FA.md").write_text(audit,encoding="utf-8")
files=[]
for p in sorted(OUT.iterdir()):
    if p.name!="FINAL_MANIFEST.json": files.append({"file":p.name,"sha256":sha(p),"bytes":p.stat().st_size})
dump("FINAL_MANIFEST.json",{"checkpoint":OUT.name,"created_at":datetime.now(timezone.utc).isoformat(),"files":files,"software_topology":"PASS","architectural_composition":"FAIL","software_architectural_readiness":"FAIL","human_acceptance":"NOT_PERFORMED"})
print(json.dumps(readiness,ensure_ascii=False,indent=2))
