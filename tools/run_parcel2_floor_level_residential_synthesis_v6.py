from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import html
import json
from pathlib import Path
import sys

from shapely.geometry import Polygon

ROOT = Path(r"<repo-root>")
sys.path.insert(0, str(ROOT / "core/architecture/reasoning"))
from parcel2_floor_level_residential_synthesis_v6 import FloorLevelResidentialSynthesisV6, verify_authority

V4 = ROOT / "exports/DEFAULT/parcel2_residential_room_planning_daylight_v4_20260913_131505/PARCEL2_RESIDENTIAL_ROOM_PLANNING_DAYLIGHT_V4.json"
EVIDENCE = ROOT / "core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json"
READ_ONLY = (
    "core/architecture/reasoning/parcel2_residential_room_planning_daylight_v3.py",
    "core/architecture/reasoning/parcel2_residential_room_planning_daylight_v4.py",
    "core/architecture/reasoning/parcel2_controlled_geometric_repair_search_v5.py",
    "tools/run_parcel2_residential_room_planning_daylight_v3.py",
    "tools/run_parcel2_residential_room_planning_daylight_v4.py",
    "tools/run_parcel2_controlled_geometric_repair_search_v5.py",
    "tests/test_parcel2_residential_room_planning_daylight_v3.py",
    "tests/test_parcel2_residential_room_planning_daylight_v4.py",
    "tests/test_parcel2_controlled_geometric_repair_search_v5.py",
    "tools/run_parcel2_h1_upper_floor_design_around_current_core_v8.py",
    "tools/run_parcel2_h1_residential_corridor_entrance_geometry_v9.py",
    "core/architecture/reasoning/architectural_precedent_experience_intelligence_v1.py",
    "core/architecture/reasoning/architectural_precedent_importer_mapping_replay_v2.py",
    "core/architecture/knowledge/architectural_precedent_experience_seed_v1.json",
    "core/architecture/knowledge/residential_floor_precedent_patterns_v1.json",
    "core/architecture/contracts/iran_topic4_room_daylight_verified_v2.json",
    "exports/DEFAULT/parcel2_residential_room_planning_daylight_v4_20260913_131505/PARCEL2_RESIDENTIAL_ROOM_PLANNING_DAYLIGHT_V4.json",
    "exports/DEFAULT/parcel2_controlled_geometric_repair_search_v5_20260913_134625/PARCEL2_CONTROLLED_GEOMETRIC_REPAIR_SEARCH_V5.json",
)


def fingerprint():
    return {name: {"sha256": sha256((ROOT/name).read_bytes()).hexdigest(), "size": (ROOT/name).stat().st_size} for name in READ_ONLY}


def _points(points, scale, x0, y1):
    return " ".join(f"{(x-x0)*scale:.1f},{(y1-y)*scale:.1f}" for x, y in points)


def render_full_floor_svg(plan, path):
    floor = Polygon(plan["floor_boundary"])
    x0, y0, x1, y1 = floor.bounds
    scale = min(760/max(x1-x0, .1), 540/max(y1-y0, .1))
    point_string = lambda points: _points(points, scale, x0, y1)
    identity = plan["identity"]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="760" viewBox="0 0 1180 760">',
        '<rect width="100%" height="100%" fill="#fbfaf6"/>',
        f'<text x="28" y="28" font-family="Arial" font-size="16" font-weight="bold">Floor-Level Residential Synthesis V6 · {html.escape(identity["topology_id"])} · {html.escape(identity["floor_id"])} · {html.escape(identity["program_hypothesis"]["id"])}</text>',
        '<text x="28" y="49" font-family="Arial" font-size="10">WHOLE FLOOR engineering/debug sheet · no render/image generation · no winner/ranking</text>',
        f'<g transform="translate(28,78)"><polygon points="{point_string(plan["floor_boundary"])}" fill="#fff" stroke="#16212b" stroke-width="5"/>',
    ]
    access = plan["core_common_access"]
    if len(access["core_polygon"]) >= 3:
        parts.append(f'<polygon points="{point_string(access["core_polygon"])}" fill="#8798a8" fill-opacity=".72" stroke="#34495e" stroke-width="2"/>')
        for key, label in (("stair_polygon", "STAIR"), ("elevator_polygon", "ELEVATOR")):
            if len(access[key]) >= 3:
                part = Polygon(access[key]); center = part.representative_point()
                parts.append(f'<polygon points="{point_string(access[key])}" fill="none" stroke="#263746" stroke-width="1.5"/>')
                parts.append(f'<text x="{(center.x-x0)*scale:.1f}" y="{(y1-center.y)*scale:.1f}" text-anchor="middle" font-family="Arial" font-size="8">{label}</text>')
    if len(access["common_corridor_polygon"]) >= 3:
        parts.append(f'<polygon points="{point_string(access["common_corridor_polygon"])}" fill="#d9d2c3" fill-opacity=".85" stroke="#685f52" stroke-width="2"/>')
    colors = {"living":"#f7dba7", "bedroom":"#c9dff2", "kitchen":"#d2e8c8", "bathroom":"#c9ece9", "service":"#ddd"}
    for index, unit in enumerate(plan["units"], 1):
        parts.append(f'<polygon points="{point_string(unit["unit_boundary"])}" fill="none" stroke="{("#7a3e9d" if index == 1 else "#aa5a00")}" stroke-width="3"/>')
        center = Polygon(unit["unit_boundary"]).representative_point()
        parts.append(f'<text x="{(center.x-x0)*scale:.1f}" y="{(y1-center.y)*scale-12:.1f}" text-anchor="middle" font-family="Arial" font-size="13" font-weight="bold">{html.escape(unit["unit_id"])}</text>')
        for circulation in unit["private_circulation"]:
            if len(circulation["polygon"]) >= 3:
                parts.append(f'<polygon points="{point_string(circulation["polygon"])}" fill="#eee8d5" fill-opacity=".9" stroke="#7b6f49" stroke-width="2"/>')
        for room in unit["rooms"]:
            if len(room["polygon"]) < 3:
                continue
            geometry = Polygon(room["polygon"]); label = geometry.representative_point()
            parts.append(f'<polygon points="{point_string(room["polygon"])}" fill="{colors.get(room["use"], "#eee")}" fill-opacity=".78" stroke="#34495e" stroke-width="1.3"/>')
            parts.append(f'<text x="{(label.x-x0)*scale:.1f}" y="{(y1-label.y)*scale:.1f}" text-anchor="middle" font-family="Arial" font-size="8">{html.escape(room["use"])} · {room["area_m2_geometry_derived"]:.1f}m²</text>')
        for door in unit["doors"]:
            x, y = door["opening"]["center"]; color = "#16794d" if door["valid"] else "#c0392b"
            parts.append(f'<circle cx="{(x-x0)*scale:.1f}" cy="{(y1-y)*scale:.1f}" r="5" fill="white" stroke="{color}" stroke-width="2"/>')
        for window in unit["windows"]:
            x, y = window["geometry"]["center"]; color = "#168aad" if window["opening_verified"] else "#d35400"
            parts.append(f'<rect x="{(x-x0)*scale-4:.1f}" y="{(y1-y)*scale-4:.1f}" width="8" height="8" fill="{color}"/>')
        lightwell = unit["lightwell"]
        if lightwell["created"] and len(lightwell["polygon"]) >= 3:
            parts.append(f'<polygon points="{point_string(lightwell["polygon"])}" fill="#b8eef5" stroke="#087f8c" stroke-width="3"/>')
    parts.append('</g>')
    status = "RESOLVED" if plan["resolved_floor_level"] else "FAIL-CLOSED · " + ", ".join(plan["spatial_problems"])
    parts.extend([
        f'<text x="28" y="650" font-family="Arial" font-size="11" fill="#922">{html.escape(status)}</text>',
        f'<text x="28" y="674" font-family="Arial" font-size="10">units={len(plan["units"])} · rooms={sum(len(u["rooms"]) for u in plan["units"])} · residual={plan["allocation"]["RESIDUAL_UNRESOLVED"]:.2f}m² · precedent-guided home zoning · geometry copied=false</text>',
        '<text x="28" y="698" font-family="Arial" font-size="10">Legend: violet/orange unit boundary · grey core · beige common/private circulation · circles doors · squares windows/daylight sources</text>',
        '</svg>',
    ])
    path.write_text("".join(parts), encoding="utf-8")


def main(out_root=ROOT/"exports/DEFAULT"):
    before = fingerprint()
    source = json.loads(V4.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    engine = FloorLevelResidentialSynthesisV6(evidence)
    output = Path(out_root) / f'parcel2_floor_level_residential_synthesis_v6_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    output.mkdir(parents=True)
    floors = []
    for _, source_plans in engine.group(source):
        floor = engine.synthesize(source_plans)
        floors.append(floor)
        ident = floor["identity"]
        render_full_floor_svg(floor, output/f'{ident["topology_id"]}-{ident["floor_id"]}-{ident["program_hypothesis"]["id"]}.svg')
    after = fingerprint()
    immutability = {name: {"before": before[name], "after": after[name], "byte_equal": before[name] == after[name]} for name in READ_ONLY}
    resolved = sum(item["resolved_floor_level"] for item in floors)
    blockers = {}
    for floor in floors:
        for issue in floor["spatial_problems"]:
            blockers[issue] = blockers.get(issue, 0) + 1
    software = {"status": "PASS" if all(v["byte_equal"] for v in immutability.values()) and verify_authority(evidence)["status"] == "PASS" else "FAIL_CLOSED",
                "authority": verify_authority(evidence), "floor_hypothesis_count": len(floors), "resolved_floor_hypothesis_count": resolved,
                "historical_inputs_immutable": all(v["byte_equal"] for v in immutability.values())}
    human = {"status": "ACCEPTED" if resolved == len(floors) else "REJECTED_FAIL_CLOSED", "resolved_floor_hypothesis_count": resolved,
             "unresolved_floor_hypothesis_count": len(floors)-resolved, "independent_from_software_acceptance": True}
    result = {"contract": "FloorLevelResidentialSynthesisV6Run", "scope": "ARCHITECTURE_ONLY",
              "pipeline_scope_exclusions": ["H2", "ELEVATOR_TRAFFIC", "STRUCTURE", "BIM", "IFC", "RENDER", "IMAGE_GENERATION"],
              "source_v4": str(V4), "selection": {"winner": None, "authoritative_ranking": False},
              "software_acceptance": software, "human_architectural_acceptance": human,
              "REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN": resolved > 0, "fully_resolved_floor_hypothesis_count": resolved,
              "next_intelligence_blockers": blockers, "immutability": immutability,
              "render": {"allowed": False, "executed": False}, "image_generation": {"allowed": False, "executed": False}, "floors": floors}
    json_path = output/"PARCEL2_FLOOR_LEVEL_RESIDENTIAL_SYNTHESIS_V6.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    entries = [{"file": item.name, "size": item.stat().st_size, "sha256": sha256(item.read_bytes()).hexdigest()} for item in sorted(output.iterdir())]
    (output/"ARTIFACT_MANIFEST.json").write_text(json.dumps({"entries": entries}, indent=2), encoding="utf-8")
    print(output)
    print(json.dumps({"software": software, "human": human, "real": result["REAL_ROOM_LEVEL_ARCHITECTURAL_DESIGN"], "blockers": blockers}, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT/"exports/DEFAULT")
