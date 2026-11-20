import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.architecture.reasoning.pilot_parking_whole_plan_topology_search_v1 import (
    PilotParkingWholePlanTopologySearchV1,
)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def pts(value, scale, ox, oy):
    return " ".join(f"{ox+x*scale:.1f},{oy-y*scale:.1f}" for x, y in value)


def poly(value, scale, ox, oy, fill, stroke, opacity=.75, width=1.5):
    return f'<polygon points="{pts(value, scale, ox, oy)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{width}"/>'


def line(value, scale, ox, oy, stroke, width=2, dash=""):
    return f'<polyline points="{pts(value, scale, ox, oy)}" fill="none" stroke="{stroke}" stroke-width="{width}" {dash}/>'


def text(x, y, value, size=14, color="#17212b", weight="normal", anchor="start"):
    return f'<text x="{x}" y="{y}" font-family="Arial" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{value}</text>'


def plan_group(study, candidate, ox, oy, scale, title=True):
    out = []
    parcel = study["local_parcel_polygon"]
    out.append(poly(parcel, scale, ox, oy, "#ffffff", "#111827", 1, 2.5))
    road = [[parcel[0][0], -2], [parcel[1][0], -2], [parcel[1][0], 0], [parcel[0][0], 0]]
    out.append(poly(road, scale, ox, oy, "#cbd5e1", "#64748b", .8))
    for field in candidate["commercial_usable_field"]:
        out.append(poly(field, scale, ox, oy, "#d9edc7", "#4d8b31", .85))
    out.append(poly(candidate["drive_lane"], scale, ox, oy, "#d7dde3", "#64748b", .75))
    out.append(poly(candidate["maneuvering_zone"], scale, ox, oy, "#c4ccd5", "#475569", .65, 2))
    out.append(poly(candidate["pedestrian_corridor"], scale, ox, oy, "#fff0a8", "#b18400", .85, 2))
    for stall in candidate["parking_stalls"]:
        out.append(poly(stall["polygon"], scale, ox, oy, "#8ecae6", "#17658a", .8, 2))
        cx = sum(x for x, _ in stall["polygon"])/4
        cy = sum(y for _, y in stall["polygon"])/4
        out.append(text(ox+cx*scale, oy-cy*scale, stall["stall_id"], 12, "#0c4a6e", "bold", "middle"))
    out.append(poly(candidate["core"]["stair"], scale, ox, oy, "#d3b5e5", "#70408c", .9))
    out.append(poly(candidate["core"]["elevator"], scale, ox, oy, "#f3c2d1", "#9d3155", .9))
    out.append(poly(candidate["core"]["lobby"], scale, ox, oy, "#f5dda8", "#9a6b12", .9))
    out.append(line(candidate["vehicle_access_axis"], scale, ox, oy, "#334155", 2, 'stroke-dasharray="7 4"'))
    out.append(line(candidate["pedestrian_path"], scale, ox, oy, "#9a6b12", 3))
    out.append(line(candidate["vehicle_entrance"], scale, ox, oy, "#0a7c59", 6))
    out.append(line(candidate["pedestrian_entrance"], scale, ox, oy, "#d49b00", 6))
    out.append(line(candidate["commercial_storefront"], scale, ox, oy, "#4d8b31", 6))
    out.append(poly(candidate["commercial_quality"]["largest_usable_rectangle"], scale, ox, oy, "none", "#1d6b34", 0, 2.5))
    if title:
        out.append(text(ox, oy-20*scale-25, candidate["candidate_id"], 20, "#17212b", "bold"))
    return out


def render_candidate(study, candidate):
    scale, ox, oy = 34, 80, 790
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="1450" height="920">', '<rect width="1450" height="920" fill="#f7f8f6"/>']
    out += plan_group(study, candidate, ox, oy, scale)
    x = 500
    q = candidate["commercial_quality"]
    out += [text(x, 70, "WHOLE-PLAN TOPOLOGY — HUMAN REVIEW", 22, "#17212b", "bold"),
            text(x, 112, f'Family: {candidate["family"]}', 16),
            text(x, 140, f'Parking: {candidate["parking_count"]} generated | independent proven: 0', 16),
            text(x, 168, f'Maneuvering: {candidate["vehicle_maneuvering_status"]}', 16, "#9a3412", "bold"),
            text(x, 196, f'Vehicle entrance: {candidate["vehicle_entrance_width"]:.2f} m (engineering design search)', 16),
            text(x, 224, f'Pedestrian entrance: {candidate["frontage_allocation"]["pedestrian_common_interval"][1]-candidate["frontage_allocation"]["pedestrian_common_interval"][0]:.2f} m', 16),
            text(x, 252, f'Commercial frontage: {q["commercial_frontage"]:.2f} m', 16),
            text(x, 280, f'Commercial area / rectangle: {q["commercial_area"]:.2f} m²', 16),
            text(x, 308, f'Commercial depth: {q["maximum_depth"]:.2f} m', 16),
            text(x, 336, f'Core: {candidate["core"]["location_classification"]}', 16),
            text(x, 364, f'Commercial quality: {candidate["commercial_quality_status"]}', 16, "#27632a", "bold"),
            text(x, 410, "FRONTAGE", 18, "#17212b", "bold"),
            text(x, 440, "Green: commercial storefront / entrance", 15),
            text(x, 468, "Gold: independent pedestrian/common entrance", 15),
            text(x, 496, "Dark green: vehicle entrance", 15),
            text(x, 542, "PLAN", 18, "#17212b", "bold"),
            text(x, 572, "Gray: direct drive lane and maneuvering zone", 15),
            text(x, 600, "Blue: generated parking stalls", 15),
            text(x, 628, "Purple/pink/gold: stair/elevator/lobby", 15),
            text(x, 656, "Light green: coherent frontage-connected commercial field", 15),
            text(x, 704, "Vehicle swept path not generated; final maneuver validation pending.", 15, "#9a3412", "bold"),
            text(x, 738, "Regulatory status: pending_rule_resolution", 15),
            text(x, 772, "No final Scenario B selection has been performed.", 15, "#17212b", "bold"),
            '</svg>']
    return "".join(out)


def render_comparison(study, candidates):
    width, height = 1800, 980
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
           '<rect width="100%" height="100%" fill="#f7f8f6"/>',
           text(45, 42, "REAL PARCEL 2 — PILOT H TOPOLOGY COMPARISON — HUMAN REVIEW", 24, "#17212b", "bold")]
    scale = 19
    for index, candidate in enumerate(candidates):
        ox = 50 + index*345
        oy = 520
        out += plan_group(study, candidate, ox, oy, scale, title=False)
        q = candidate["commercial_quality"]
        out += [text(ox, 570, candidate["candidate_id"], 14, "#17212b", "bold"),
                text(ox, 595, f'Parking {candidate["parking_count"]} | pending vehicle model', 13),
                text(ox, 620, f'Frontage C/P/V: {q["commercial_frontage"]:.2f} / 1.20 / {candidate["vehicle_entrance_width"]:.2f} m', 13),
                text(ox, 645, f'Commercial {q["commercial_area"]:.1f} m² | depth {q["maximum_depth"]:.1f} m', 13),
                text(ox, 670, f'Core {candidate["core"]["location_classification"]}', 13)]
    out += [text(45, 735, "Legend: green commercial | gray vehicle | yellow pedestrian | blue parking | purple/pink/gold core", 15),
            text(45, 770, "All plans use REAL Parcel 2 normalized geometry. No candidate is finally selected.", 15, "#17212b", "bold"),
            text(45, 805, "All maneuvering results remain pending_vehicle_model_validation.", 15, "#9a3412", "bold"), '</svg>']
    return "".join(out)


def png(svg_path, png_path, profile):
    chrome = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    if chrome.exists():
        subprocess.run([str(chrome), "--headless", "--no-sandbox", "--disable-gpu",
                        f"--user-data-dir={profile}", "--hide-scrollbars", "--window-size=1800,980",
                        f"--screenshot={png_path}", svg_path.as_uri()], check=True)


def main():
    base_path = sorted((ROOT/"exports"/"DEFAULT").glob("parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json"))[-1]
    rec_path = sorted((ROOT/"exports"/"DEFAULT").glob("parcel2_basement_v2_*/program_alternative_recommendation_v1_*/PARCEL2_PROGRAM_ALTERNATIVE_RECOMMENDATION_V1.json"))[-1]
    base = json.loads(base_path.read_text()); rec = json.loads(rec_path.read_text())
    protected = deepcopy(base); before = fingerprint(protected)
    result = PilotParkingWholePlanTopologySearchV1().resolve(base["site"], base["requirements"], rec["baseline_scenario_a"])
    if fingerprint(base) != before:
        raise RuntimeError("Scenario A mutation detected")
    result["source_baseline_contract_path"] = str(base_path)
    result["baseline_contract_preservation_fingerprint"] = before
    folder = base_path.parent/("pilot_h_topology_search_v1_"+datetime.now().strftime("%Y%m%d_%H%M%S")); folder.mkdir()
    contract_path = folder/"PARCEL2_PILOT_H_TOPOLOGY_SEARCH_V1.json"
    contract_path.write_text(json.dumps(result, indent=2))
    outputs = []
    for candidate in result["promising_candidates"]:
        svg_path = folder/f'{candidate["candidate_id"]}.svg'; png_path = svg_path.with_suffix(".png")
        svg_path.write_text(render_candidate(result, candidate), encoding="utf-8")
        png(svg_path, png_path, folder/f'.chrome_{candidate["candidate_id"]}')
        outputs.append({"candidate_id": candidate["candidate_id"], "svg": str(svg_path), "png": str(png_path) if png_path.exists() else None})
    comparison = folder/"PARCEL2_PILOT_H_BEST_CANDIDATES_COMPARISON.svg"
    comparison.write_text(render_comparison(result, result["promising_candidates"]), encoding="utf-8")
    comparison_png = comparison.with_suffix(".png"); png(comparison, comparison_png, folder/'.chrome_comparison')
    print(json.dumps({"contract": str(contract_path), "candidate_count": result["candidate_count"],
                      "hard_valid": result["hard_valid_candidate_count"], "promising": outputs,
                      "comparison_svg": str(comparison), "comparison_png": str(comparison_png) if comparison_png.exists() else None,
                      "final_selection_performed": False, "program_changed": False, "basement_deleted": False}))


if __name__ == "__main__":
    main()
