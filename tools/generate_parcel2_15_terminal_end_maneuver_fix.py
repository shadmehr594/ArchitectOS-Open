"""Generate the terminal END + maneuver-only review artifact from recorded V3."""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.terminal_ramp_floor_alignment_v1 import TerminalRampFloorAlignmentV1
from tools.generate_parcel2_basement_v2_design import View, svg_to_png, text


V3 = ROOT / "exports/DEFAULT/parcel2_basement_v2_20260909_143231_229427/edge_controlled_v3_20260909_230806/PARCEL2_15_EDGE_CONTROLLED_TOPOLOGY_V3.json"


def main():
    recorded = json.loads(V3.read_text(encoding="utf-8"))
    source_path = sorted((ROOT / "exports/DEFAULT").glob("parcel2_basement_v2_*/PARCEL2_BASEMENT_V2_CONTRACT.json"))[-1]
    base = json.loads(source_path.read_text(encoding="utf-8"))
    helper = BasementRampParkingDesignReasonerV2()
    frame = helper._frame(base["site"]["parcel"], base["site"]["frontage"])
    inner = helper._to_local_polygon(base["physical_basement_wall"]["inner_face"], frame)
    search = TerminalRampFloorAlignmentV1().resolve(recorded["new_search"]["candidates"], inner)
    source_candidates = [c for c in recorded["new_search"]["candidates"] if c["geometry_status"] == "hard_valid"]
    old = min(source_candidates, key=lambda c: abs(c["physical_path_length"]["path_length_margin"]))
    valid = [c for c in search["candidates"] if c["geometry_status"] == "hard_valid"]
    best_valid = max(valid, key=lambda c: (c["maneuvering_dimensions"][0], c["alignment"]["terminal_length"])) if valid else None
    best_attempt = min(search["candidates"], key=lambda c: (len(c["failure_reasons"]),
        "terminal_leg_outside_clear_face" in c["failure_reasons"],
        "maneuvering_field_outside_clear_face" in c["failure_reasons"],
        c["ramp_maneuver_overlap_area"] + c["terminal_maneuver_overlap_area"]))
    records = [old_record(old), attempt_record(best_attempt), valid_record(best_valid)]
    contract = {
        "contract": "Parcel2TerminalEndManeuverFixComparison",
        "input_v3_contract": str(V3), "v3_search_rerun": False,
        "input_hard_valid_v3_candidates": len(source_candidates),
        "terminal_search_candidates": len(search["candidates"]),
        "hard_valid_terminal_arrivals": len(valid),
        "search_status": search["status"], "comparison_records": records,
        "parking_search_status": "not_run_terminal_arrival_validation",
        "physical_ramp_published": False, "human_visual_acceptance": "pending",
    }
    folder = source_path.parent / ("terminal_end_maneuver_fix_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    folder.mkdir()
    json_path = folder / "PARCEL2_15_TERMINAL_END_MANEUVER_FIX.json"
    svg_path = folder / "PARCEL2_15_TERMINAL_END_MANEUVER_FIX.svg"
    png_path = folder / "PARCEL2_15_TERMINAL_END_MANEUVER_FIX.png"
    json_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
    svg_path.write_text(render(records, inner, contract), encoding="utf-8")
    svg_to_png(svg_path, png_path)
    print(json.dumps({"folder": str(folder), "png": str(png_path), "json": str(json_path),
        "input_v3_candidates": len(source_candidates), "terminal_candidates": len(search["candidates"]),
        "hard_valid": len(valid), "status": search["status"]}))


def old_record(c):
    ramp = PolygonCompat(c["surface"])
    field = PolygonCompat(c["maneuvering_field"])
    return {"label": "A — CURRENT V3 PROBLEM", "status": "invalid_terminal_arrival",
        "ramp": c["surface"], "centerline": c["topology"]["centerline"],
        "end": c["topology"]["end_edge"], "field": c["maneuvering_field"],
        "overlap": ramp.intersection(field).area, "candidate_id": c["candidate_id"],
        "failure": "diagonal_END_and_maneuver_overlaps_sloped_ramp"}


def attempt_record(c):
    return _record("B — BEST TERMINAL-ALIGNED ATTEMPT", c)


def valid_record(c):
    if c is None:
        return {"label": "C — VALID END + MANEUVER FIELD", "status": "not_generated"}
    return _record("C — VALID END + MANEUVER FIELD", c)


def _record(label, c):
    a = c["alignment"]
    return {"label": label, "status": c["geometry_status"], "candidate_id": c["candidate_id"],
        "ramp": c["source_ramp_surface"], "centerline": c["source_ramp_centerline"],
        "terminal_surface": a["terminal_surface"], "terminal_path": a["steering_transition_centerline"] + [a["terminal_leg_end"]],
        "end": a["end_edge"], "field": c["maneuvering_field"], "vehicle_path": c["vehicle_path"],
        "return_path": c["return_path"], "terminal_length": a["terminal_length"],
        "heading": a["terminal_heading_name"], "end_width": a["end_edge_width"],
        "end_z": [a["end_left"][2], a["end_midpoint"][2], a["end_right"][2]],
        "interface": c["end_interface_width"], "overlap": c["ramp_maneuver_overlap_area"],
        "terminal_overlap": c["terminal_maneuver_overlap_area"], "maneuver": c["maneuvering_dimensions"],
        "failure": ", ".join(c["failure_reasons"]) if c["failure_reasons"] else "none"}


def render(records, inner, contract):
    view = View(list(inner.exterior.coords)[:-1]); w, h = 2040, 1260
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><rect width="100%" height="100%" fill="#f7f6f1"/>',
        text(40, 44, "REAL PARCEL 2 — 15% TERMINAL END + MANEUVER FIX", 27, "bold"),
        text(40, 73, "RECORDED V3 INPUT ONLY — V3 SEARCH RERUN: FALSE — PARKING NOT RUN", 16, "bold")]
    for i, r in enumerate(records):
        x = 24 + i * 674; y = 96
        out += [f'<rect x="{x}" y="{y}" width="650" height="1100" rx="8" fill="white" stroke="#8296a2" stroke-width="2"/>', text(x+18, y+34, r["label"], 18, "bold")]
        if r["status"] == "not_generated":
            out += [text(x+325, y+490, "NOT GENERATED", 28, "bold", "#b01630", "middle"),
                    text(x+325, y+530, "No terminal END + downstream field passed", 15, "normal", "#b01630", "middle")]
            continue
        out.append(f'<svg x="{x+18}" y="{y+55}" width="614" height="690" viewBox="0 0 1900 1300" preserveAspectRatio="xMidYMid meet">')
        out.append(f'<polygon points="{view.points(list(inner.exterior.coords)[:-1])}" fill="#edf1ef" stroke="#263a43" stroke-width="6"/>')
        out.append(f'<polygon points="{view.points(r["ramp"])}" fill="#efb3bf" fill-opacity=".65" stroke="#a61734" stroke-width="4"/>')
        if r.get("terminal_surface"): out.append(f'<polygon points="{view.points(r["terminal_surface"])}" fill="#f6c46d" fill-opacity=".72" stroke="#a46100" stroke-width="4"/>')
        if r.get("field"): out.append(f'<polygon points="{view.points(r["field"])}" fill="#9fd9ad" fill-opacity=".62" stroke="#176f37" stroke-width="6"/>')
        if r.get("centerline"): out.append(f'<polyline points="{view.points(r["centerline"])}" fill="none" stroke="#0865af" stroke-width="6" stroke-dasharray="14 9"/>')
        if r.get("terminal_path"): out.append(f'<polyline points="{view.points(r["terminal_path"])}" fill="none" stroke="#8a5500" stroke-width="7"/>')
        if r.get("vehicle_path"): out.append(f'<polyline points="{view.points(r["vehicle_path"])}" fill="none" stroke="#075fa8" stroke-width="7" stroke-dasharray="18 10"/>')
        out.append(f'<polyline points="{view.points(r["end"])}" fill="none" stroke="#541128" stroke-width="12"/>')
        out.append('</svg>')
        lines = [f"Candidate: {r['candidate_id']}"]
        if i == 0:
            lines += ["END: diagonal / embedded in field", f"Ramp–maneuver overlap: {r['overlap']:.3f} m²", "INVALID TERMINAL ARRIVAL"]
        else:
            lines += [f"Terminal leg: {r['terminal_length']:.3f} m", f"Heading: {r['heading']}",
                f"END width / interface: {r['end_width']:.3f} / {r['interface']:.3f} m",
                f"END L/C/R Z: {r['end_z'][0]:.2f} / {r['end_z'][1]:.2f} / {r['end_z'][2]:.2f} m",
                f"Maneuver: {r['maneuver'][0]:.1f} x {r['maneuver'][1]:.1f} m",
                f"Ramp overlap: {r['overlap']:.3f} m² | terminal overlap: {r['terminal_overlap']:.3f} m²",
                f"Failure: {r['failure']}", f"STATUS: {r['status']}"]
        for j, line in enumerate(lines):
            red = "INVALID" in line or "Failure:" in line or "not_feasible" in line
            out.append(text(x+18, y+785+j*29, line, 14, "bold" if red or "STATUS" in line else "normal", "#b01630" if red else "#20272c"))
    footer = f"{contract['terminal_search_candidates']} TERMINAL COMBINATIONS | {contract['hard_valid_terminal_arrivals']} HARD-VALID | HUMAN ACCEPTANCE PENDING"
    out += [text(40, 1236, footer, 15, "bold", "#155b2c" if contract['hard_valid_terminal_arrivals'] else "#b01630"), '</svg>']
    return ''.join(out)


def PolygonCompat(points):
    from shapely.geometry import Polygon
    return Polygon(points)


if __name__ == "__main__":
    main()
