"""Parcel 2 H1 V3 minimal-corridor architecture-only human-review output."""
from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime
from pathlib import Path

from shapely.geometry import Polygon

from core.architecture.reasoning.generic_minimal_access_corridor_optimizer_v1 import (
    GenericMinimalAccessCorridorOptimizerV1,
)

ROOT = Path(__file__).resolve().parents[1]
V2_DIR = ROOT / "exports/DEFAULT/parcel2_h1_access_first_v2_20260912_201359"
V2_JSON = V2_DIR / "PARCEL2_H1_ACCESS_FIRST_V2.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def svg_points(poly, scale, ox, oy, minx, maxy):
    return " ".join(f"{ox + (x-minx)*scale:.1f},{oy + (maxy-y)*scale:.1f}" for x, y in poly)


def polygon_element(coords, pp, fill, stroke, opacity=.45, dash=""):
    if not coords:
        return ""
    return f'<polygon points="{pp(coords)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" {dash}/>'


def render_candidate(report, candidate):
    parcel = report["parcel"]
    xs, ys = [p[0] for p in parcel], [p[1] for p in parcel]
    minx, maxy = min(xs), max(ys)
    scale = min(700/(max(xs)-min(xs)), 700/(max(ys)-min(ys)))
    ox, oy = 70, 140
    pp = lambda p: svg_points(p, scale, ox, oy, minx, maxy)
    m = candidate["metrics"]
    body = [
        polygon_element(parcel, pp, "#ffffff", "#111827", .1),
        polygon_element(candidate["direct_commercial_street_frontage_region"], pp, "#f59e0b", "#b45309", .38),
        polygon_element(candidate["aisle_manoeuvre"], pp, "#cbd5e1", "#475569", .55),
        polygon_element(candidate["public_pedestrian_path"], pp, "#22c55e", "#15803d", .13),
        polygon_element(candidate["pedestrian_shared_with_manoeuvre_region"], pp, "#86efac", "#166534", .42, 'stroke-dasharray="6 3"'),
        polygon_element(candidate["vehicle_corridor"], pp, "#a855f7", "#7e22ce", .28),
        polygon_element(candidate["temp_core"], pp, "#f3d28f", "#9a6500", .65),
    ]
    for stall in candidate["stalls"]:
        body.append(polygon_element(stall["polygon"], pp, "#60a5fa", "#1d4ed8", .62))
    core = Polygon(candidate["temp_core"])
    mincx, mincy, maxcx, maxcy = core.bounds
    shaft = [[mincx,mincy],[mincx+2.1,mincy],[mincx+2.1,mincy+2.1],[mincx,mincy+2.1]]
    body.extend([
        polygon_element(shaft, pp, "none", "#be185d", 0, 'stroke-width="2" stroke-dasharray="5 3"'),
        f'<path d="M {pp([[mincx,mincy],[maxcx,maxcy]])}" stroke="#6d28d9" stroke-width="3" stroke-dasharray="5 3"/>',
        f'<path d="M {pp([[maxcx,mincy],[mincx,maxcy]])}" stroke="#6d28d9" stroke-width="3" stroke-dasharray="5 3"/>',
        f'<polyline points="{pp(candidate["vehicle_corridor_axis"])}" fill="none" stroke="#7e22ce" stroke-width="4" marker-end="url(#arrow)"/>',
        f'<polyline points="{pp(report["frontage"])}" fill="none" stroke="#dc2626" stroke-width="7"/>',
    ])
    labels = (
        f'PARKING {candidate["parking_count"]} | COMMERCIAL {m["new_commercial_candidate_area_m2"]:.2f} m² | ALL GATES {str(candidate["all_gates_pass"]).upper()}',
        f'VEHICLE CORRIDOR old {m["old_vehicle_corridor_length_m"]:.2f}m / {m["old_vehicle_corridor_area_m2"]:.2f}m² → new {m["new_minimal_vehicle_corridor_length_m"]:.2f}m / {m["new_minimal_vehicle_corridor_area_m2"]:.2f}m²',
        f'RECLAIMED CORRIDOR {m["reclaimed_corridor_area_m2"]:.2f}m² | COMMERCIAL GAIN {m["commercial_area_gain_m2"]:.2f}m² | SHARED PED {m["pedestrian_shared_area_m2"]:.2f}m²',
        'TEMP CORE — NOT COMMERCIAL | 2-FLIGHT STAIR SCHEMATIC/NON-FINAL | TEMP ELEVATOR 2.10×2.10m',
        'LOBBY / SPATIAL SIZING UNRESOLVED | NO WINNER',
    )
    text = "".join(f'<text x="70" y="{900+i*24}" font-family="Arial" font-size="16">{html.escape(line)}</text>' for i, line in enumerate(labels))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1050" height="1040">
<defs><marker id="arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="#7e22ce"/></marker></defs>
<rect width="100%" height="100%" fill="#f8fafc"/><text x="50" y="42" font-family="Arial" font-size="24" font-weight="bold">H1 V3 — {html.escape(candidate["candidate_id"])}</text>
<text x="50" y="72" font-family="Arial" font-size="14">RED frontage | ORANGE commercial | CREAM temp core | BLUE stalls | GREY manoeuvre | PURPLE minimal vehicle | GREEN public/shared pedestrian</text>
{''.join(body)}{text}</svg>'''


def render_index(report, artifacts):
    rows = []
    for i, candidate in enumerate(report["candidates"]):
        m = candidate["metrics"]
        rows.append(f'''<g transform="translate(35,{95+i*92})"><rect width="1130" height="74" rx="8" fill="#fff" stroke="#cbd5e1"/>
<text x="16" y="24" font-family="Arial" font-size="15" font-weight="bold">{html.escape(candidate["candidate_id"])}</text>
<text x="16" y="49" font-family="Arial" font-size="13">P {candidate["parking_count"]} | corridor {m["old_vehicle_corridor_length_m"]:.2f}m/{m["old_vehicle_corridor_area_m2"]:.2f}m² → {m["new_minimal_vehicle_corridor_length_m"]:.2f}m/{m["new_minimal_vehicle_corridor_area_m2"]:.2f}m² | reclaimed {m["reclaimed_corridor_area_m2"]:.2f}m² | commercial {m["new_commercial_candidate_area_m2"]:.2f}m² | gates {str(candidate["all_gates_pass"]).upper()}</text></g>''')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="610"><rect width="100%" height="100%" fill="#f8fafc"/>
<text x="35" y="42" font-family="Arial" font-size="23" font-weight="bold">Parcel 2 H1 Access-First V3 — human-review index</text>
<text x="35" y="68" font-family="Arial" font-size="14">Five independent SVG plans accompany this index. READY={str(report["h1_ready_for_human_architectural_selection"]).upper()} | NO WINNER | H2 PARKED</text>{''.join(rows)}</svg>'''


def main(output_root=None):
    v2 = load(V2_JSON)
    domain = {"polygon": v2["parcel"], "floor_scope": "ground_pilotis", "evidence_status": "resolved"}
    frontage = {"segment": v2["frontage"], "status": "confirmed"}
    optimized = GenericMinimalAccessCorridorOptimizerV1().optimize(domain, frontage, v2["candidates"])
    candidates = optimized["candidates"]
    ready = bool(candidates) and all(c["all_gates_pass"] for c in candidates)
    report = {
        "contract": "Parcel2H1AccessFirstMinimalCorridorDiagnosticV3",
        "generated_at": datetime.now().astimezone().isoformat(),
        "scope": "architecture_only",
        "lineage": {"v2_json_path": str(V2_JSON), "v2_json_sha256": digest(V2_JSON), "v2_mutated": False},
        "parcel": v2["parcel"], "frontage": v2["frontage"],
        "policy": "maximize_residual_after_mandatory_allocations",
        "corridor_termination_policy": "geometry_derived_furthest_required_stall_to_aisle_access_boundary",
        "pedestrian_circulation_policy": "shared_with_manoeuvre_where_geometry_allows; exclusive_footprint_only_is_mandatory_duplicate",
        "candidate_count": len(candidates), "candidates": candidates,
        "final_selection_performed": False, "winner": None,
        "h1_ready_for_human_architectural_selection": ready,
        "h2_status": "parked_not_evaluated",
        "temp_core_status_unchanged": True,
        "prohibited_workflows_executed": {"elevator_traffic": False, "structure": False, "BIM": False, "IFC": False, "render": False, "image_generation": False},
        "blockers": [] if ready else [c["candidate_id"] for c in candidates if not c["all_gates_pass"]],
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = (Path(output_root) if output_root else ROOT / "exports/DEFAULT") / f"parcel2_h1_access_first_v3_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    json_path = out / "PARCEL2_H1_ACCESS_FIRST_V3.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    candidate_files = []
    for candidate in candidates:
        path = out / f'{candidate["candidate_id"]}.svg'
        path.write_text(render_candidate(report, candidate), encoding="utf-8")
        candidate_files.append({"candidate_id": candidate["candidate_id"], "path": str(path), "sha256": digest(path)})
    index_path = out / "PARCEL2_H1_ACCESS_FIRST_V3_INDEX.svg"
    index_path.write_text(render_index(report, candidate_files), encoding="utf-8")
    manifest = {"json_path": str(json_path), "json_sha256": digest(json_path), "candidate_svgs": candidate_files,
                "index_svg_path": str(index_path), "index_svg_sha256": digest(index_path), "ready": ready}
    manifest_path = out / "ARTIFACT_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    manifest["manifest_sha256"] = digest(manifest_path)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


if __name__ == "__main__":
    main()
