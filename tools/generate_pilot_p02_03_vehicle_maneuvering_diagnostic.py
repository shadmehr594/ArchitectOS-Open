import json
import subprocess
import sys
from pathlib import Path

from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.architecture.reasoning.vehicle_movement_path_diagnostic_v1 import (
    VehicleMovementPathDiagnosticV1,
)


def points(value, scale, ox, oy):
    return " ".join(f"{ox + x*scale:.2f},{oy - y*scale:.2f}" for x, y in value)


def polygon(value, scale, ox, oy, fill, stroke, opacity=1.0, width=1.5):
    return f'<polygon points="{points(value, scale, ox, oy)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{width}"/>'


def polyline(value, scale, ox, oy, stroke, width=2, dash=""):
    return f'<polyline points="{points(value, scale, ox, oy)}" fill="none" stroke="{stroke}" stroke-width="{width}" {dash}/>'


def label(x, y, value, size=15, color="#17212b", weight="normal"):
    return f'<text x="{x}" y="{y}" font-family="Arial" font-size="{size}" fill="{color}" font-weight="{weight}">{value}</text>'


def render_svg(study, candidate, diagnostic):
    scale, ox, oy = 35, 90, 790
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="920" viewBox="0 0 1500 920">',
           '<rect width="1500" height="920" fill="#f7f8f6"/>',
           label(60, 42, "PILOT-P02-03 VEHICLE MANEUVERING DIAGNOSTIC — BEFORE", 24, "#17212b", "bold"),
           label(60, 69, "REAL Parcel 2 | contract geometry | no topology redesign", 15, "#52606d")]
    parcel = study["local_parcel_polygon"]
    out.append(polygon(parcel, scale, ox, oy, "#ffffff", "#111827", 1, 3))
    road = [[parcel[0][0], -2.2], [parcel[1][0], -2.2], [parcel[1][0], 0], [parcel[0][0], 0]]
    out.append(polygon(road, scale, ox, oy, "#c9d5df", "#60788a", .75))
    out.append(label(ox + 90, oy + 55, "10 m ROAD / PUBLIC ACCESS", 14, "#36566d", "bold"))
    for field in candidate["commercial_usable_field"]:
        out.append(polygon(field, scale, ox, oy, "#d9edc7", "#669944", .8))
    out.append(polygon(candidate["parking_aisle"], scale, ox, oy, "#d8dde3", "#64748b", .7))
    colors = ["#8ecae6", "#90cdf4"]
    for index, stall in enumerate(candidate["parking_stalls"]):
        out.append(polygon(stall, scale, ox, oy, colors[index], "#17658a", .65, 2))
        c = Polygon(stall).centroid
        out.append(label(ox+c.x*scale-18, oy-c.y*scale, f"P-{index+1:02d}", 15, "#0c4a6e", "bold"))
    out.append(polygon(candidate["core"]["stair"], scale, ox, oy, "#d3b5e5", "#70408c", .85))
    out.append(polygon(candidate["core"]["elevator"], scale, ox, oy, "#f3c2d1", "#9d3155", .9))
    out.append(polygon(candidate["core"]["common_lobby"], scale, ox, oy, "#f5dda8", "#9a6b12", .9))
    out.append(polygon(candidate["pedestrian_circulation"], scale, ox, oy, "#fff0a8", "#b18400", .8, 2))
    out.append(polyline(candidate["vehicle_entrance"], scale, ox, oy, "#0a7c59", 6))
    for attempt in diagnostic["attempts"]:
        out.append(polygon(attempt["clearance_corridor"], scale, ox, oy, "#ef4444", "#b91c1c", .13, 1.5))
        out.append(polyline(attempt["generated_center_trajectory"], scale, ox, oy, "#d11a2a", 3))
        out.append(polyline(attempt["exit_center_trajectory"], scale, ox, oy, "#7c3aed", 2, 'stroke-dasharray="8 5"'))
        for outside in attempt["outside_drivable_field_geometry"]:
            out.append(polygon(outside, scale, ox, oy, "#ff4d00", "#7f1d1d", .55, 2))
        for hit in attempt["occupied_stall_collisions"]:
            for collision in hit["intersection_polygon"]:
                out.append(polygon(collision, scale, ox, oy, "#a90000", "#5f0000", .7, 2))
    out += [label(ox+10, oy-705, "FRONTAGE / VEHICLE ENTRANCE", 13, "#087454", "bold"),
            label(ox+178, oy-335, "OUTSIDE DRIVABLE FIELD", 13, "#a32600", "bold"),
            label(ox+183, oy-172, "COLLISION WITH OCCUPIED STALL", 13, "#820000", "bold"),
            label(ox+205, oy-48, "CORE / STALL OVERLAP", 12, "#6b1450", "bold")]
    lx = 520
    out += [label(lx, 115, "LEGEND", 20, "#17212b", "bold"),
            label(lx, 150, "Gray: drivable aisle", 15), label(lx, 178, "Blue: stalls / occupied-stall obstacles", 15),
            label(lx, 206, "Red line: generated entry center trajectory", 15),
            label(lx, 234, "Purple dashed: exit = reversed entry", 15),
            label(lx, 262, "Pale red: 5.0 m clearance-corridor approximation", 15),
            label(lx, 290, "Orange/red: exact failure intersections", 15),
            label(lx, 338, "MODEL EVIDENCE", 19, "#17212b", "bold"),
            label(lx, 370, "Vehicle dimensions: unresolved", 15),
            label(lx, 394, "Actual occupied vehicle footprint: unavailable", 15, "#9a3412", "bold"),
            label(lx, 418, "Turning radius input: 5.0 m; not consumed by V3", 15),
            label(lx, 446, "Strategies: one quadratic entry; reversed path exit", 15),
            label(lx, 474, "Swept vehicle footprint: not implemented", 15),
            label(lx, 502, "Primary classification: vehicle_path_intelligence_limitation", 15, "#9a3412", "bold"),
            label(lx, 530, "Candidate layout: independently invalid (core/stall overlap)", 15, "#9a3412", "bold"),
            label(lx, 578, "FAILURE AREAS", 19, "#17212b", "bold")]
    y = 608
    for attempt in diagnostic["attempts"]:
        collision_area = sum(item["intersection_area"] for item in attempt["occupied_stall_collisions"])
        out.append(label(lx, y, f'{attempt["stall_id"]}: outside={attempt["outside_drivable_field_area"]:.3f} m² | occupied collision={collision_area:.3f} m²', 15))
        y += 28
    out += [f'<line x1="{lx}" y1="690" x2="{lx+5*scale}" y2="690" stroke="#111827" stroke-width="3"/>',
            label(lx, 682, "0", 13), label(lx+5*scale-12, 682, "5 m SCALE", 13),
            label(lx, 760, "No design geometry was changed. Regulatory status: pending_rule_resolution", 14, "#52606d"),
            '</svg>']
    return "".join(out)


def main():
    study_path = sorted((ROOT / "exports" / "DEFAULT").glob("parcel2_basement_v2_*/pilot_parking_feasibility_study_v1_*/PARCEL2_PILOT_PARKING_FEASIBILITY_STUDY_V1.json"))[-1]
    study = json.loads(study_path.read_text(encoding="utf-8"))
    candidate = next(c for c in study["candidates"] if c["candidate_id"] == "PILOT-P02-03")
    baseline_path = Path(study["source_baseline_contract_path"])
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    diagnostic = VehicleMovementPathDiagnosticV1().analyze(candidate, baseline)
    output_dir = study_path.parent / "vehicle_maneuvering_diagnostic_v1"
    output_dir.mkdir(exist_ok=True)
    json_path = output_dir / "PILOT-P02-03_VEHICLE_MANEUVERING_DIAGNOSTIC.json"
    svg_path = output_dir / "PILOT-P02-03_VEHICLE_MANEUVERING_DIAGNOSTIC.svg"
    before_path = output_dir / "PILOT-P02-03_vehicle_path_before.svg"
    json_path.write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
    svg = render_svg(study, candidate, diagnostic)
    svg_path.write_text(svg, encoding="utf-8")
    before_path.write_text(svg, encoding="utf-8")
    png_path = output_dir / "PILOT-P02-03_VEHICLE_MANEUVERING_DIAGNOSTIC.png"
    chrome = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    if chrome.exists():
        subprocess.run([str(chrome), "--headless", "--no-sandbox", "--disable-gpu",
                        f"--user-data-dir={output_dir / '.chrome'}", "--hide-scrollbars",
                        "--window-size=1500,920", f"--screenshot={png_path}", svg_path.as_uri()], check=True)
    print(json.dumps({"json": str(json_path), "svg": str(svg_path), "before_svg": str(before_path),
                      "png": str(png_path) if png_path.exists() else None,
                      "classification": diagnostic["failure_classification"]}))


if __name__ == "__main__":
    main()
