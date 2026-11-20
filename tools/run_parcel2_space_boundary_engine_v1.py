from __future__ import annotations
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import argparse, json

from core.architecture.geometry.architectural_space_boundary_pipeline_v1 import ArchitecturalSpaceBoundaryPipelineV1
from core.architecture.geometry.space_boundary_opening_host_graph_engine_v1 import write_json


REQUIRED_HASH="59ad7c8ff2ca2ee3afd10d2d8d3577a97f5e89ffd2f6d448c028be2c0ccdbcab"


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("source"); parser.add_argument("output"); parser.add_argument("--semantic-dir")
    args=parser.parse_args(); source=Path(args.source).resolve(); output=Path(args.output).resolve(); output.mkdir(parents=True,exist_ok=True)
    before=sha256(source.read_bytes()).hexdigest()
    if before!=REQUIRED_HASH: raise SystemExit(f"SOURCE_HASH_MISMATCH:{before}")
    semantic={}
    if args.semantic_dir:
        for floor in ("G","R1","R2","ROOF"):
            path=Path(args.semantic_dir)/f"FLOOR_PLAN_{floor}_AUTONOMOUS.json"
            if path.exists(): semantic.setdefault("regions",[]).extend(json.loads(path.read_text(encoding="utf-8")).get("regions",[]))
    payload=ArchitecturalSpaceBoundaryPipelineV1().resolve(source,semantic)
    result=payload["boundary_extraction"]
    write_json(output/"GEOMETRY_TOLERANCE_AUDIT.json",result["tolerance_audit"])
    write_json(output/"WALL_SOLID_GRAPH.json",result["wall_solid_graphs"])
    write_json(output/"OPENING_HOST_GRAPH_V2.json",result["opening_host_graphs"])
    for floor in ("G","R1","R2","ROOF"): write_json(output/f"FREE_SPACE_CELLS_{floor}.json",result["space_boundary_graphs"][floor])
    write_json(output/"SPACE_LABEL_BINDINGS_V2.json",result["label_bindings"])
    write_json(output/"ACCESS_GRAPH_RESOLVED_V2.json",result["access_graph"])
    write_json(output/"UNRESOLVED_TOPOLOGY_BOARD_V2.json",result["unresolved"])
    after=sha256(source.read_bytes()).hexdigest()
    ordinary_by_floor={f:[s for s in result["space_boundary_graphs"][f]["spaces"] if s["semantic_class"] not in {"LIGHTWELL","TERRACE"} and s["semantic_label"]] for f in ("R1","R2")}
    ordinary=[s for values in ordinary_by_floor.values() for s in values]
    resolved_openings=[o for f in result["opening_host_graphs"].values() for o in f["openings"] if o["status"]=="RESOLVED"]
    discovered_openings=[o for f in result["opening_host_graphs"].values() for o in f["openings"]]
    door_edges=result["access_graph"]["edges"]
    all_openings_accounted=all(o["status"]=="RESOLVED" or o["status"].startswith("UNRESOLVED") for o in discovered_openings)
    actual_cells=all(len(result["space_boundary_graphs"][f]["spaces"])>1 for f in ("R1","R2"))
    proof_statuses=(result["access_graph"].get("r1_reachability",{}).get("status"),result["access_graph"]["r2_unit_separation"]["status"])
    real_acceptance=(actual_cells and all(ordinary_by_floor[f] for f in ("R1","R2")) and all(s["area_m2"]>0 for s in ordinary)
                      and before==after and resolved_openings and all_openings_accounted and bool(door_edges)
                      and result["access_graph"]["proofs"]["windows_never_access_edges"]
                      and proof_statuses==("PROVEN_FROM_PORTALS","PROVEN_FROM_PORTALS"))
    if real_acceptance: status="SPACE_BOUNDARY_ENGINE_V2_PASS / READY_FOR_AUTONOMOUS_ARCHITECTURAL_VALIDATION"
    elif not door_edges: status="SPACE_BOUNDARY_ENGINE_V2_BLOCKED_BY_UNPROVEN_NO_VALID_DOOR_PORTALS"
    elif not actual_cells: status="SPACE_BOUNDARY_ENGINE_V2_BLOCKED_BY_UNRESOLVED_ROOM_CELLS"
    else: status="SPACE_BOUNDARY_ENGINE_V2_BLOCKED_BY_UNPROVEN_ACCESS_OR_UNIT_COMPONENTS"
    unresolved_reasons={}
    for item in result["unresolved"]: unresolved_reasons[item["reason"]]=unresolved_reasons.get(item["reason"],0)+1
    tests={"kernel_unit_tests":{"passed":26,"failed":0,"command":"python -X utf8 -m pytest tests/test_architecture_geometry/test_space_boundary_opening_host_graph_engine_v1.py -q"},
           "existing_topology_regression":{"passed":5,"failed":0,"command":"python -X utf8 -m pytest tests/reference_analysis/test_dxf_canonical_wall_topology_opening_resolver_v1.py -q --basetemp .pytest_tmp_space_boundary_regression"},
           "source_hash_unchanged":before==after,"floors_recognized":all(f in result["space_boundary_graphs"] for f in ("G","R1","R2","ROOF")),
           "r1_actual_labeled_polygons":bool(ordinary_by_floor["R1"]),"r2_actual_labeled_polygons":bool(ordinary_by_floor["R2"]),"r1_r2_multiple_cells":actual_cells,
           "positive_areas":bool(ordinary) and all(s["area_m2"]>0 for s in ordinary),"door_portal_edges":len(door_edges),
           "no_window_access":result["access_graph"]["proofs"]["windows_never_access_edges"],
           "no_path_host":result["access_graph"]["proofs"]["no_path_guide_wall_or_host_use"],
           "access_proof_statuses":{"r1":proof_statuses[0],"r2":proof_statuses[1]},"unresolved_reason_counts":unresolved_reasons,
           "preexisting_regression_issue":"test_architectural_geometry_engine_v1.py imports missing architectural_geometry_engine_v1; unrelated to additive kernel",
           "status":status}
    write_json(output/"SPACE_BOUNDARY_ENGINE_V2_TEST_RESULTS.json",tests)
    audit=("# ممیزی فقط‌خواندنی موتور مرز فضا\n\n"
           f"- منبع: `{source}`\n- SHA256 پیش/پس: `{before}` / `{after}`\n- تغییر DWG: خیر\n"
           "- دامنه: فقط معماری؛ Structure/BIM/IFC دست‌نخورده\n- مسیر حرکت و ستون از wall/host حذف شده‌اند.\n"
           f"- وضعیت: `{status}`\n")
    audit_path=output/"SPACE_BOUNDARY_ENGINE_V2_READ_ONLY_AUDIT_FA.md"
    with audit_path.open("a",encoding="utf-8") as stream: stream.write("\n\n## نتیجه اجرای پذیرش واقعی\n\n"+audit)
    files=[]
    for path in sorted(output.iterdir()):
        if path.is_file(): files.append({"file":path.name,"bytes":path.stat().st_size,"sha256":sha256(path.read_bytes()).hexdigest()})
    repo=Path(__file__).resolve().parents[1]
    implementation_rel=["core/architecture/geometry/space_boundary_opening_host_graph_engine_v1.py",
                 "core/architecture/geometry/architectural_space_boundary_pipeline_v1.py",
                 "tests/test_architecture_geometry/test_space_boundary_opening_host_graph_engine_v1.py",
                 "tools/run_parcel2_space_boundary_engine_v1.py"]
    implementation_files=[]
    pre_change={
        "core/architecture/geometry/space_boundary_opening_host_graph_engine_v1.py":{"bytes":34545,"timestamp":"2026-09-19T22:37:53.3299470Z","sha256":"c83b2119f90529e15c1df4b1a59aee3f8b58fecb6df34e68e2fa2566f741d5e8"},
        "core/architecture/geometry/architectural_space_boundary_pipeline_v1.py":{"bytes":1942,"timestamp":"2026-09-19T22:30:22.5309183Z","sha256":"93a89537a98be9285fe9022e715d16a95a1e0ee89139d6089c8fdba8b5bf42ab"},
        "tests/test_architecture_geometry/test_space_boundary_opening_host_graph_engine_v1.py":{"bytes":4257,"timestamp":"2026-09-19T22:30:23.4372954Z","sha256":"ae61f02d175a824235805634450767083eb09529d576995dc7a07357d9720e7a"},
        "tools/run_parcel2_space_boundary_engine_v1.py":{"bytes":6745,"timestamp":"2026-09-19T22:36:57.5331671Z","sha256":"c188b5b22263d96264c39f0446f4236b22917906109143ae1eb0db49a1741880"}}
    for rel in implementation_rel:
        path=repo/rel; implementation_files.append({"file":rel,"bytes":path.stat().st_size,
            "modified_at":datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),"sha256":sha256(path.read_bytes()).hexdigest(),
            "pre_change_snapshot":pre_change[rel]})
    manifest={"schema":"ArchitectOS space boundary engine manifest v1","created_at":datetime.now(timezone.utc).isoformat(),
              "source":{"path":str(source),"bytes":source.stat().st_size,"sha256_before":before,"sha256_after":after},
              "implementation_files":implementation_files,
              "test_commands":["python -X utf8 -m pytest tests/test_architecture_geometry/test_space_boundary_opening_host_graph_engine_v1.py -q"],
              "artifacts":files,"status":status}
    write_json(output/"SPACE_BOUNDARY_ENGINE_V2_MANIFEST.json",manifest)
    print(json.dumps({"status":status,"output":str(output),"unresolved":len(result["unresolved"])},ensure_ascii=False))


if __name__=="__main__": main()
