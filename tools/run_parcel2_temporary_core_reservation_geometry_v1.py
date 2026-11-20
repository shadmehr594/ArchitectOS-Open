"""Run Parcel 2 H1/H2 architecture-only diagnostics with a temporary core proxy."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from shapely.geometry import Polygon
from shapely.ops import unary_union

from core.architecture.reasoning.basement_ramp_parking_design_reasoner_v2 import BasementRampParkingDesignReasonerV2
from core.architecture.reasoning.generic_core_reservation_placement_v1 import GenericCoreReservationPlacementV1
from core.architecture.reasoning.generic_pilotis_parking_geometry_producer_v1 import GenericPilotisParkingGeometryProducerV1


ROOT = Path(__file__).resolve().parents[1]
ASSUMPTION_PATH = ROOT / "core/architecture/contracts/parcel2_temporary_core_reservation_design_assumption_v1.json"
BASEMENT_PATH = ROOT / "exports/DEFAULT/parcel2_basement_v2_20260909_143231_229427/PARCEL2_BASEMENT_V2_CONTRACT.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_svg(report):
    polygons = []
    for item in report["core_placement_hypotheses"]["candidates"]:
        polygons.append(("core", item["candidate_id"], item["polygon"]))
    for branch in report["branches"]["H1"]["runs"]:
        for candidate in branch["result"].get("candidates", [])[:2]:
            for stall in candidate.get("stall_geometries", []):
                polygons.append(("h1_stall", branch["core_candidate_id"], stall["polygon"]))
    for candidate in report["branches"]["H2"]["result"].get("candidates", []):
        if candidate.get("geometry_status") == "candidate":
            polygons.append(("h2_ramp", candidate["candidate_id"], candidate["ramp"]["polygon"]))
            for stall in candidate.get("parking_stalls", []):
                polygons.append(("h2_stall", candidate["candidate_id"], stall))
            if len(polygons) > 120:
                break
    domain = report["domain"]["common_core_stack_domain"]
    all_points = [p for _, _, poly in polygons for p in poly] + domain
    xs, ys = [p[0] for p in all_points], [p[1] for p in all_points]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    scale = min(900 / max(maxx-minx, 1), 650 / max(maxy-miny, 1))
    def pts(poly):
        return " ".join(f"{60+(x-minx)*scale:.2f},{710-(y-miny)*scale:.2f}" for x, y in poly)
    styles = {"core": "fill:#f2c14e;fill-opacity:.22;stroke:#a66b00;stroke-width:1",
              "h1_stall": "fill:#4f86c6;fill-opacity:.12;stroke:#285a92;stroke-width:.7",
              "h2_ramp": "fill:#d1495b;fill-opacity:.10;stroke:#9b2235;stroke-width:.7",
              "h2_stall": "fill:#52b788;fill-opacity:.12;stroke:#26734d;stroke-width:.7"}
    body = [f'<polygon points="{pts(domain)}" style="fill:none;stroke:#111;stroke-width:2"/>']
    for kind, ident, poly in polygons:
        body.append(f'<polygon points="{pts(poly)}" style="{styles[kind]}"><title>{kind}: {ident}</title></polygon>')
    return ("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1020\" height=\"780\" viewBox=\"0 0 1020 780\">"
            "<rect width=\"100%\" height=\"100%\" fill=\"white\"/>"
            "<text x=\"40\" y=\"30\" font-family=\"sans-serif\" font-size=\"16\">Parcel 2 — H1/H2 core-reservation diagnostic (non-final)</text>"
            + "".join(body) + "</svg>")


def main():
    assumption = load(ASSUMPTION_PATH)
    old = load(BASEMENT_PATH)
    parcel = old["site"]["parcel"]
    frontage = old["site"]["frontage"]
    inner = old["physical_basement_wall"]["inner_face"]
    common = Polygon(parcel).intersection(Polygon(inner))
    domain_evidence = {
        "polygon": [list(p) for p in list(common.exterior.coords)[:-1]],
        "floor_scope": "ground_and_basement_core_stack",
        "evidence_status": "resolved",
        "provenance": [{"source": str(BASEMENT_PATH), "role": "actual_parcel_and_inner_clear_domain"}],
    }
    placements = GenericCoreReservationPlacementV1().produce(domain_evidence, assumption)
    parking_requirement = {
        "minimum_required_capacity": 3,
        "stall_width": 2.5,
        "stall_depth": 5.0,
        "aisle_width": 5.0,
        "provenance": [{"source": "parcel2_human_program_evidence_v1_and_current_project_test_dimensions"}],
    }
    h1_runs = []
    for core in placements["candidates"]:
        inventory = {
            "inventory_complete": True,
            "regions": [{"region_id": core["candidate_id"], "kind": "core", "polygon": core["polygon"]}],
            "provenance": [{"source": assumption["contract"], "authority_class": "DESIGN_ASSUMPTION"}],
        }
        result = GenericPilotisParkingGeometryProducerV1().produce(
            domain_evidence={**domain_evidence, "floor_scope": "ground_pilotis"},
            parking_requirement=parking_requirement,
            protected_region_evidence=inventory,
            vehicle_access_candidate_region={"status": "candidate_region_not_point", "segment": frontage},
            branch_evidence={"hypothesis_id": "H1", "provenance": [{"source": "H1_independent_run"}]},
        )
        h1_runs.append({"core_candidate_id": core["candidate_id"], "result": result})

    requirements = dict(old["requirements"])
    requirements["parking"] = dict(requirements["parking"], minimum_count=3)
    requirements["core"] = {"evidence_used": [assumption["contract"]], "shape_proxy": True, "final_geometry": False}
    h2 = BasementRampParkingDesignReasonerV2().design(
        parcel, frontage, old["physical_basement_wall"], requirements,
        {"inventory_status": "complete_empty"},
        core_placement_candidates=placements["candidates"], allow_selection=False)

    h1_geometry_count = sum(item["result"].get("candidate_count", 0) for item in h1_runs)
    h2_geometry_count = len(h2.get("candidates", []))
    h2_valid_count = sum(c.get("geometry_status") == "candidate" for c in h2.get("candidates", []))
    residuals = []
    ground = Polygon(domain_evidence["polygon"])
    for run in h1_runs:
        core = next(c for c in placements["candidates"] if c["candidate_id"] == run["core_candidate_id"])
        for candidate in run["result"].get("candidates", []):
            occupied = [Polygon(core["polygon"]), Polygon(candidate["candidate_geometry"]["aisle"])]
            occupied += [Polygon(s["polygon"]) for s in candidate["stall_geometries"]]
            allocated = unary_union(occupied)
            residuals.append({
                "branch": "H1", "core_candidate_id": core["candidate_id"],
                "parking_candidate_id": candidate["candidate_id"],
                "ground_floor_geometric_residual_m2": round(ground.difference(allocated).area, 6),
                "commercial_area_status": "not_yet_legitimate_due_to_unresolved_access_and_pedestrian_allocations",
                "commercial_area_m2": None,
            })
    report = {
        "contract": "Parcel2TemporaryCoreReservationGeometryDiagnosticV1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "scope": "architecture_only",
        "assumption_contract": str(ASSUMPTION_PATH),
        "assumption_contract_sha256": sha256(ASSUMPTION_PATH),
        "temporary_proxy_accepted_by_contracts": placements["status"] == "candidates_produced" and h2.get("core_sizing", {}).get("geometry_status") == "resolved",
        "domain": {"source": str(BASEMENT_PATH), "common_core_stack_domain": domain_evidence["polygon"]},
        "core_placement_hypotheses": placements,
        "branches": {
            "H1": {"candidate_count": h1_geometry_count, "runs": h1_runs,
                   "validation_status": "candidate_only_access_and_pedestrian_unresolved"},
            "H2": {"candidate_count": h2_geometry_count, "hard_valid_candidate_count": h2_valid_count,
                   "result": h2, "validation_status": "candidate_only_no_selection"},
        },
        "commercial_residual": {"policy": "maximize_after_mandatory_allocations", "legitimate_area_m2": None,
                                "diagnostic_ground_residuals": residuals},
        "population_occupancy": {"status": "unresolved", "blocked_geometry": False},
        "winner_selected_between_H1_H2": False,
        "prohibited_workflows_executed": {"structure": False, "BIM": False, "IFC": False, "render": False},
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "exports/DEFAULT" / f"parcel2_temporary_core_reservation_geometry_v1_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    json_path = out / "PARCEL2_TEMPORARY_CORE_RESERVATION_GEOMETRY_V1.json"
    svg_path = out / "PARCEL2_TEMPORARY_CORE_RESERVATION_GEOMETRY_V1.svg"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    svg_path.write_text(render_svg(report), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "json_sha256": sha256(json_path),
                      "svg": str(svg_path), "svg_sha256": sha256(svg_path),
                      "core_hypotheses": placements["candidate_count"],
                      "h1_candidates": h1_geometry_count, "h2_candidates": h2_geometry_count,
                      "h2_hard_valid": h2_valid_count}, indent=2))


if __name__ == "__main__":
    main()
