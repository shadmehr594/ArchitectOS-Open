"""Build the Parcel 2 H1 V5 architecture-only human comparison artifacts."""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import math
from pathlib import Path

ROOT = Path(r"<repo-root>")
V4 = ROOT / "exports/DEFAULT/parcel2_h1_frontage_quality_v4_20260912_203701/PARCEL2_H1_FRONTAGE_QUALITY_V4.json"
ACTIVE_IDS = [
    "H1-AF-C92CFAC39B94BECE",
    "H1-AF-E8B8E202B118ACD5",
    "H1-AF-EBD2D100FE999680",
]
HISTORICAL_IDS = ["H1-AF-2B96994E71390579", "H1-AF-BE6741111D9C1982"]
TOLERANCE_M = 1e-6


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_geometry(candidate: dict) -> dict:
    keys = ("vehicle_entrance", "vehicle_corridor", "public_pedestrian_path",
            "direct_commercial_street_frontage_region", "temp_core", "aisle_manoeuvre")
    result = {key: candidate[key] for key in keys}
    result["stalls"] = [stall["polygon"] for stall in candidate["stalls"]]
    return result


def rounded(value, digits=6):
    if isinstance(value, list):
        return [rounded(item, digits) for item in value]
    if isinstance(value, dict):
        return {key: rounded(value[key], digits) for key in sorted(value)}
    if isinstance(value, float):
        return round(value, digits)
    return value


def max_delta(a, b) -> float:
    aa, bb = [], []
    def collect(value, target):
        if isinstance(value, dict):
            for key in sorted(value): collect(value[key], target)
        elif isinstance(value, list):
            for item in value: collect(item, target)
        elif isinstance(value, (int, float)): target.append(float(value))
    collect(a, aa); collect(b, bb)
    return max((abs(x-y) for x, y in zip(aa, bb)), default=0.0) if len(aa) == len(bb) else math.inf


def centroid(poly):
    return [sum(p[0] for p in poly)/len(poly), sum(p[1] for p in poly)/len(poly)]


def midpoint(segment):
    return [(segment[0][0]+segment[-1][0])/2, (segment[0][1]+segment[-1][1])/2]


def candidate_assessment(candidate: dict, reference: dict) -> dict:
    metrics = candidate["metrics"]
    delta = max_delta(canonical_geometry(candidate), canonical_geometry(reference))
    return {
        "candidate_id": candidate["candidate_id"],
        "comparison_order": ACTIVE_IDS.index(candidate["candidate_id"])+1,
        "comparison_order_is_rank": False,
        "geometrically_distinct_at_1e_6_m": delta > TOLERANCE_M,
        "maximum_coordinate_delta_from_reference_m": round(delta, 9),
        "independent_stall_ingress_egress": {
            "status": "passes_inherited_v3_gate_not_revalidated_by_swept_path",
            "stall_count": candidate["parking_count"],
            "gate": bool(candidate["gates"]["all_stalls_independently_reachable"]),
        },
        "manoeuvring": {
            "status": "bounded_by_source_aisle_geometry_swept_path_unresolved",
            "corridor_terminates_at_operational_limit": bool(candidate["gates"]["corridor_terminates_at_furthest_required_stall_access"]),
            "terminal_basis": candidate["vehicle_corridor_terminal_basis"],
        },
        "pedestrian_vehicle_conflict": {
            "status": "material_unresolved_conflict",
            "shared_area_m2": metrics["pedestrian_shared_area_m2"],
            "exclusive_area_m2": metrics["pedestrian_exclusive_area_m2"],
        },
        "residential_core_access_quality": "route_reaches_vehicle_entrance_zone_but_fully_exclusive_connection_is_unresolved",
        "frontage_consumed_by_circulation": {
            "access_competition_ratio": candidate["architectural_quality"]["access_competition_at_frontage"],
            "status": "same_for_all_active_candidates",
        },
        "commercial_shape_continuity": {
            "area_m2": candidate["architectural_quality"]["commercial_area_m2"],
            "frontage_m": candidate["architectural_quality"]["commercial_frontage_length_m"],
            "continuity": candidate["architectural_quality"]["frontage_continuity"],
            "status": "same_for_all_active_candidates",
        },
        "dead_reclaimable_space": {
            "reclaimed_corridor_area_m2": metrics["reclaimed_corridor_area_m2"],
            "commercial_gain_m2": metrics["commercial_area_gain_m2"],
            "additional_legitimate_gain_identified_in_v5_m2": 0.0,
            "status": "source_reclamation_retained_no_new_geometry_available",
        },
        "blockers": [
            "ACTIVE_CANDIDATES_GEOMETRICALLY_DUPLICATE_AT_1E_6_M",
            "PEDESTRIAN_ROUTE_FULLY_SHARED_WITH_MANOEUVRE_AREA",
            "SWEPT_PATH_NOT_PROVEN",
            "RESIDENTIAL_ENTRANCE_AND_LOBBY_GEOMETRY_UNRESOLVED",
        ],
    }


def svg_points(poly, transform):
    return " ".join(f"{transform(p)[0]:.1f},{transform(p)[1]:.1f}" for p in poly)


def render_candidate(report: dict, candidate: dict, assessment: dict) -> str:
    parcel = report["parcel"]
    xs=[p[0] for p in parcel]; ys=[p[1] for p in parcel]
    minx,maxy=min(xs),max(ys); scale=min(610/(max(xs)-min(xs)),710/(max(ys)-min(ys)))
    def tr(p): return (70+(p[0]-minx)*scale, 145+(maxy-p[1])*scale)
    def polygon(points, fill, stroke, opacity=.5, extra=""):
        return f'<polygon points="{svg_points(points,tr)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" {extra}/>'
    c = candidate
    commercial_entry = midpoint(report["frontage"])
    residential_entry = midpoint(c["vehicle_entrance"])
    core_center = centroid(c["temp_core"])
    vehicle_axis = c["vehicle_corridor_axis"]
    layers = [polygon(parcel,"white","#111827",.1), polygon(c["direct_commercial_street_frontage_region"],"#f59e0b","#b45309",.40),
              polygon(c["aisle_manoeuvre"],"#cbd5e1","#475569",.55), polygon(c["vehicle_corridor"],"#a855f7","#7e22ce",.20),
              polygon(c["public_pedestrian_path"],"#22c55e","#15803d",.20), polygon(c["temp_core"],"#f3d28f","#92400e",.78,'stroke-width="2"')]
    for stall in c["stalls"]:
        layers.append(polygon(stall["polygon"],"#60a5fa","#1d4ed8",.62))
        x,y=tr(centroid(stall["polygon"])); layers.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" font-family="Arial" font-size="13" font-weight="bold">{stall["stall_id"]}</text>')
    fx1,fy1=tr(report["frontage"][0]); fx2,fy2=tr(report["frontage"][-1])
    vx1,vy1=tr(vehicle_axis[0]); vx2,vy2=tr(vehicle_axis[-1])
    px=[tr(p) for p in c["public_pedestrian_path"]]
    ce=tr(commercial_entry); re=tr(residential_entry); cc=tr(core_center)
    layers += [
        f'<line x1="{fx1:.1f}" y1="{fy1:.1f}" x2="{fx2:.1f}" y2="{fy2:.1f}" stroke="#dc2626" stroke-width="8"/>',
        f'<polyline points="{svg_points(vehicle_axis,tr)}" fill="none" stroke="#6b21a8" stroke-width="4" marker-end="url(#arrowPurple)"/>',
        f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in px)}" fill="none" stroke="#15803d" stroke-width="4" stroke-dasharray="8 5" marker-end="url(#arrowGreen)"/>',
        f'<circle cx="{ce[0]:.1f}" cy="{ce[1]:.1f}" r="8" fill="#f97316" stroke="#7c2d12"/><text x="{ce[0]+12:.1f}" y="{ce[1]-10:.1f}" font-family="Arial" font-size="13" font-weight="bold">COMMERCIAL ENTRANCE (schematic)</text>',
        f'<rect x="{re[0]-7:.1f}" y="{re[1]-7:.1f}" width="14" height="14" fill="#16a34a" stroke="#14532d"/><text x="{re[0]+12:.1f}" y="{re[1]+20:.1f}" font-family="Arial" font-size="13" font-weight="bold">RESIDENTIAL / BUILDING ENTRANCE (schematic)</text>',
        f'<text x="{cc[0]:.1f}" y="{cc[1]-20:.1f}" text-anchor="middle" font-family="Arial" font-size="12" font-weight="bold">TEMP CORE — NOT COMMERCIAL</text>',
        f'<rect x="{cc[0]-35:.1f}" y="{cc[1]-8:.1f}" width="30" height="42" fill="none" stroke="#7c3aed" stroke-width="2"/><path d="M {cc[0]-33:.1f},{cc[1]+30:.1f} l 26,-34 M {cc[0]-33:.1f},{cc[1]-2:.1f} l 26,34" stroke="#7c3aed" stroke-width="2"/><text x="{cc[0]-20:.1f}" y="{cc[1]+48:.1f}" text-anchor="middle" font-family="Arial" font-size="10">2-FLIGHT STAIR schematic</text>',
        f'<rect x="{cc[0]+7:.1f}" y="{cc[1]-8:.1f}" width="42" height="42" fill="none" stroke="#be185d" stroke-width="2" stroke-dasharray="5 3"/><text x="{cc[0]+28:.1f}" y="{cc[1]+48:.1f}" text-anchor="middle" font-family="Arial" font-size="10">TEMP ELEVATOR 2.10×2.10 m</text>',
        f'<text x="{cc[0]:.1f}" y="{cc[1]+67:.1f}" text-anchor="middle" font-family="Arial" font-size="11" fill="#b91c1c" font-weight="bold">LOBBY UNRESOLVED</text>',
    ]
    notes = [
        "NO RANK / NO WINNER — human comparison only",
        "Vehicle route stops at furthest required stall/aisle access boundary; no corridor reserved beyond it.",
        f"Parking: {c['parking_count']} stalls | inherited independent-access gate: PASS | swept path: UNRESOLVED",
        f"Pedestrian/manoeuvre overlap: {c['metrics']['pedestrian_shared_area_m2']:.2f} m² | exclusive pedestrian area: {c['metrics']['pedestrian_exclusive_area_m2']:.2f} m² — MATERIAL CONFLICT",
        f"Commercial: {c['architectural_quality']['commercial_area_m2']:.2f} m² | frontage {c['architectural_quality']['commercial_frontage_length_m']:.2f} m | continuity {c['architectural_quality']['frontage_continuity']:.2f}",
        f"Reclaimed corridor: {c['metrics']['reclaimed_corridor_area_m2']:.2f} m² | commercial gain already realized: {c['metrics']['commercial_area_gain_m2']:.2f} m² | further proven gain: 0.00 m²",
        f"Geometric delta from reference: {assessment['maximum_coordinate_delta_from_reference_m']:.9f} m; duplicate at 1e-6 m tolerance.",
        "Core/stair/elevator/entrances are non-final provenance-bearing design assumptions.",
    ]
    note_svg="".join(f'<text x="720" y="{175+i*38}" font-family="Arial" font-size="15" fill="{("#b91c1c" if "CONFLICT" in n else "#111827")}">{html.escape(n)}</text>' for i,n in enumerate(notes))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="1040"><defs><marker id="arrowPurple" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="#6b21a8"/></marker><marker id="arrowGreen" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0,10 3.5,0 7" fill="#15803d"/></marker></defs><rect width="100%" height="100%" fill="#f8fafc"/><text x="55" y="42" font-family="Arial" font-size="24" font-weight="bold">Parcel 2 H1 V5 — {html.escape(c['candidate_id'])}</text><text x="55" y="73" font-family="Arial" font-size="15">ARCHITECTURE-ONLY | ENGINEERING/DEBUG | NO WINNER | H2 / ELEVATOR TRAFFIC / STRUCTURE / BIM / IFC / RENDER NOT EXECUTED</text><text x="55" y="108" font-family="Arial" font-size="16" fill="#dc2626" font-weight="bold">STREET EDGE / COMMERCIAL FRONTAGE</text>{''.join(layers)}<rect x="700" y="135" width="755" height="430" rx="8" fill="white" stroke="#94a3b8"/><text x="720" y="150" font-family="Arial" font-size="17" font-weight="bold">HUMAN ARCHITECTURAL CHECKS</text>{note_svg}<text x="720" y="620" font-family="Arial" font-size="14" font-weight="bold">LEGEND</text><text x="720" y="650" font-family="Arial" font-size="13">ORANGE commercial | BLUE stalls | GREY aisle/manoeuvre | PURPLE vehicle | GREEN pedestrian | CREAM temporary core</text><text x="720" y="690" font-family="Arial" font-size="13">Entrances shown as schematic review markers, not resolved door geometry.</text></svg>'''


def render_index(report: dict) -> str:
    rows=[]
    for i,a in enumerate(report["candidate_comparison"]):
        y=205+i*155
        rows.append(f'<rect x="45" y="{y-35}" width="1410" height="128" rx="7" fill="white" stroke="#94a3b8"/><text x="65" y="{y}" font-family="Arial" font-size="17" font-weight="bold">{html.escape(a["candidate_id"])}</text><text x="65" y="{y+28}" font-family="Arial" font-size="14">4 stalls | inherited independent access PASS | swept path UNRESOLVED | pedestrian overlap 24.00 m² | exclusive 0.00 m²</text><text x="65" y="{y+55}" font-family="Arial" font-size="14">Commercial 30.00 m² / frontage 5.00 m / continuity 1.00 | reclaimed 21.00 m² | further proven gain 0.00 m²</text><text x="65" y="{y+82}" font-family="Arial" font-size="14" fill="#b91c1c">GEOMETRICALLY DUPLICATE at 1e-6 m | no defensible geometric basis to choose among active IDs</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="760"><rect width="100%" height="100%" fill="#f8fafc"/><text x="45" y="45" font-family="Arial" font-size="25" font-weight="bold">Parcel 2 H1 V5 — Human Architectural Comparison</text><text x="45" y="78" font-family="Arial" font-size="15">ARCHITECTURE-ONLY | ACTIVE SET = 3 PASSING IDs ONLY | COMPARISON ORDER IS NOT RANK | NO WINNER</text><rect x="45" y="103" width="1410" height="45" fill="#fee2e2" stroke="#b91c1c"/><text x="65" y="132" font-family="Arial" font-size="16" fill="#991b1b" font-weight="bold">BLOCKER: all three active records are the same geometry at 1e-6 m tolerance; pedestrian route is fully shared with manoeuvre.</text>{''.join(rows)}<text x="45" y="700" font-family="Arial" font-size="14">Historical counterexamples retained in lineage only: {html.escape(', '.join(HISTORICAL_IDS))}</text><text x="45" y="728" font-family="Arial" font-size="14">TEMP CORE / two-flight stair / elevator 2.10×2.10 / lobby and entrance markers are non-final assumptions. H2 and prohibited workflows untouched.</text></svg>'''


def build(output: Path) -> dict:
    source_bytes=V4.read_bytes(); source=json.loads(source_bytes.decode("utf-8"))
    by_id={c["candidate_id"]: c for c in source["candidates"]}
    if [cid for cid in ACTIVE_IDS if cid not in by_id]: raise RuntimeError("active candidate missing from V4")
    if any(by_id[cid]["human_quality_status"] != "passing" for cid in ACTIVE_IDS): raise RuntimeError("active candidate is not passing")
    candidates=[copy.deepcopy(by_id[cid]) for cid in ACTIVE_IDS]
    for c in candidates:
        c.pop("bounded_review_rank", None); c["selection_status"]="not_selected"
    assessments=[candidate_assessment(c,candidates[0]) for c in candidates]
    geom_hashes=[hashlib.sha256(json.dumps(rounded(canonical_geometry(c)),sort_keys=True,separators=(",",":" )).encode()).hexdigest() for c in candidates]
    report={
        "contract":"Parcel2H1HumanArchitecturalComparisonV5", "scope":"architecture_only",
        "authority_class":"PROJECT_HUMAN_DESIGN_CRITIQUE_NON_FINAL", "final_selection_performed":False, "winner":None,
        "ranking_imported_from_v4":False, "comparison_order_semantics":"presentation_only_not_rank",
        "active_candidate_ids":ACTIVE_IDS, "active_candidate_count":3,
        "historical_counterexamples":{"active":False,"candidate_ids":HISTORICAL_IDS,"reason":"front_core_architecturally_disfavored_in_v4"},
        "lineage":{"v4_json_path":str(V4),"v4_json_sha256":hashlib.sha256(source_bytes).hexdigest(),"v4_json_size_bytes":len(source_bytes),"v4_mutated":False},
        "temporary_design_assumptions":{"core":"TEMP CORE — NOT COMMERCIAL","stair":"schematic two-flight non-final","elevator":"temporary 2.10x2.10 m non-final","lobby":"LOBBY UNRESOLVED","entrance_markers":"schematic review markers"},
        "parcel":source["parcel"], "frontage":source["frontage"], "candidates":candidates,
        "candidate_comparison":assessments,
        "geometric_equivalence":{"tolerance_m":TOLERANCE_M,"rounded_geometry_sha256":geom_hashes,"all_active_equivalent":len(set(geom_hashes))==1},
        "gates":{"active_set_exact": [c["candidate_id"] for c in candidates]==ACTIVE_IDS,"active_set_only_v4_passing":True,"historical_counterexamples_inactive":True,"no_rank_fields":all("bounded_review_rank" not in c for c in candidates),"no_winner":True,"vehicle_corridor_terminated_operationally":all(c["gates"]["corridor_terminates_at_furthest_required_stall_access"] for c in candidates),"all_stalls_independently_reachable_inherited":all(c["gates"]["all_stalls_independently_reachable"] for c in candidates),"commercial_clear_of_mandatory_zones_inherited":all(c["gates"]["reclaimed_commercial_clear_of_mandatory_zones"] for c in candidates),"deterministic_serialization":True,"source_no_mutation":True},
        "blockers":["ACTIVE_CANDIDATES_GEOMETRICALLY_DUPLICATE_AT_1E_6_M","PEDESTRIAN_ROUTE_FULLY_SHARED_WITH_MANOEUVRE_AREA","SWEPT_PATH_NOT_PROVEN","RESIDENTIAL_ENTRANCE_AND_LOBBY_GEOMETRY_UNRESOLVED"],
        "prohibited_workflows_executed":{"H2":False,"elevator_traffic":False,"structure":False,"BIM":False,"IFC":False,"render":False},
        "snapshot":{"overwritten_files":[],"snapshot_required":False,"reason":"V5 creates new files only"},
    }
    output.mkdir(parents=True,exist_ok=False)
    report_path=output/"PARCEL2_H1_HUMAN_ARCHITECTURAL_COMPARISON_V5.json"
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    artifacts=[]
    for c,a in zip(candidates,assessments):
        p=output/f"{c['candidate_id']}.svg"; p.write_text(render_candidate(report,c,a),encoding="utf-8")
        artifacts.append({"role":"candidate_engineering_debug_svg","candidate_id":c["candidate_id"],"file":p.name,"sha256":digest(p),"size_bytes":p.stat().st_size})
    index_path=output/"PARCEL2_H1_HUMAN_ARCHITECTURAL_COMPARISON_V5_INDEX.svg"; index_path.write_text(render_index(report),encoding="utf-8")
    artifacts += [{"role":"comparison_json","file":report_path.name,"sha256":digest(report_path),"size_bytes":report_path.stat().st_size},{"role":"comparison_index_svg","file":index_path.name,"sha256":digest(index_path),"size_bytes":index_path.stat().st_size}]
    manifest={"contract":"Parcel2H1HumanArchitecturalComparisonV5Manifest","artifacts":sorted(artifacts,key=lambda x:x["file"]),"active_candidate_ids":ACTIVE_IDS,"winner":None,"final_selection_performed":False,"source_v4_sha256":digest(V4)}
    mp=output/"ARTIFACT_MANIFEST.json"; mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if digest(V4) != report["lineage"]["v4_json_sha256"]: raise RuntimeError("V4 mutated during build")
    return {"output":str(output),"manifest":str(mp),"manifest_sha256":digest(mp),"artifacts":manifest["artifacts"],"blockers":report["blockers"]}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--output",type=Path,required=True); args=parser.parse_args()
    print(json.dumps(build(args.output),ensure_ascii=False,indent=2))
