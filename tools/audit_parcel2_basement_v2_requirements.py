"""Fail-closed requirements audit for the real Parcel 2 basement V2 checkpoint.

This tool reads the real site source and existing diagnostic artifacts.  It
does not invoke ArchitecturalBrain, generate a layout, or publish geometry.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from core.cad.cad_import_engine import CADImportEngine
from core.site.separation_joint_engine import SeparationJointEngine
from core.site.separation_joint_engine import SeparationJointEngine


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "data" / "real_site" / "parcel_2_source.dxf"
PREVIOUS = ROOT / "exports" / "DEFAULT" / "basement_ramp_parking_v2_south_20260908_230910_327693"


def item(value, source_file, source_contract, authority, reason=None):
    result = {
        "value": value,
        "source_file": str(source_file),
        "source_contract": source_contract,
        "classification": authority,
    }
    if reason:
        result["reason"] = reason
    return result


def main():
    cad = CADImportEngine().load({"file_object": str(SOURCE)}, target_parcel=2)
    site = cad["site"]
    constraints = site["site_constraints"]
    access = constraints["access"]
    parcel = site["points"]
    edge = [parcel[access["edge_index"]], parcel[(access["edge_index"] + 1) % len(parcel)]]

    previous_evidence = json.loads(
        (PREVIOUS / "PARCEL2_RAMP_DIAGNOSTIC_EVIDENCE.json").read_text(encoding="utf-8")
    )
    requirements = {
        "source": "user_project_requirement",
        "evidence_status": "authoritative_for_current_test",
        "levels": {"ground": 0.0, "basement": -2.4, "ramp_arrival": -2.4},
        "ramp": {"clear_width": 3.5, "maximum_longitudinal_slope": 0.15,
                 "required_headroom": 2.2},
        "basement": {"coverage_policy": "maximum_feasible"},
        "basement_wall": {"thickness": 0.20, "geometric_height": 2.40},
        "separation": {"road_edge": 0.0, "neighbor_edges": 0.1},
        "parking": {"minimum_count": 2, "stall_width": 2.5, "stall_depth": 5.0,
                    "aisle_width": 5.0, "minimum_turning_radius": 5.0},
        "core": {"maximum_width": 4.5, "maximum_depth": 5.5,
                 "elevator_required": True, "elevator_lobby": [1.5, 1.5]},
        "parking_pedestrian": {"required_clear_width": 1.2},
    }
    requirements["ramp"]["derived_minimum_run"] = abs(
        requirements["levels"]["basement"] - requirements["levels"]["ground"]
    ) / requirements["ramp"]["maximum_longitudinal_slope"]
    envelope = SeparationJointEngine().resolve_buildable_envelope(
        parcel,
        {"edge_offsets": [0.0, 0.10, 0.10, 0.10],
         "source": requirements["source"],
         "evidence_status": requirements["evidence_status"]},
    )
    wall_centerline = SeparationJointEngine().resolve_buildable_envelope(
        parcel, {"edge_offsets": [0.10, 0.20, 0.20, 0.20]},
    )
    wall_inner_face = SeparationJointEngine().resolve_buildable_envelope(
        parcel, {"edge_offsets": [0.20, 0.30, 0.30, 0.30]},
    )

    parcel_fixture = ROOT / "tests" / "architecture_generation" / "test_basement_ramp_parcel2_acceptance_v2.py"
    missing = [
        "minimum_resolved_core_footprint_or_core_sizing_contract",
        "complete_fixed_obstacle_and_conflict_inventory",
    ]
    audit = {
        "checkpoint": "REAL Parcel 2 Basement / Ramp / Parking Generative Design V2",
        "status": "pending_requirement",
        "first_proven_boundary": "physical_basement_wall_assembly_requirements",
        "project_requirements": requirements,
        "buildable_basement_envelope": envelope,
        "physical_wall_geometry": {
            "outer_face": envelope.get("buildable_boundary"),
            "centerline": wall_centerline.get("buildable_boundary"),
            "inner_face": wall_inner_face.get("buildable_boundary"),
            "thickness": 0.20,
            "geometric_height": 2.40,
            "clear_height": None,
            "neighbor_boundary_clearance": 0.10,
            "separation_preserved_to_outer_face": True,
        },
        "source": {
            "file": str(SOURCE),
            "parcel_polygon": parcel,
            "parcel_area": site["area"],
            "vehicle_access_edge": edge,
            "road_width": access.get("road_width"),
            "access_evidence": access,
            "adjacency_evidence": constraints.get("adjacency"),
            "north_evidence": constraints.get("north"),
            "fixed_obstacle_inventory": {
                "status": "unresolved_not_proven_complete",
                "reason": (
                    "The source contains additional unclassified CAD entities, while the "
                    "site contract publishes no authoritative fixed-obstacle inventory."
                ),
                "may_be_treated_as_complete_empty": False,
            },
        },
        "value_provenance": {
            "basement_buildable_envelope": item(envelope.get("buildable_boundary"), Path(__file__),
                "maximum feasible envelope after explicit per-edge separation",
                "DERIVED_GEOMETRIC_CONSTRAINT", "This is not yet a physical wall footprint."),
            "f1_footprint": item(previous_evidence["f1_footprint"], parcel_fixture,
                "_real_parcel2_intent.resolved_dimensions + layout/geometry", "FALLBACK_TEST_FIXTURE",
                "The resulting footprint extends outside Parcel 2 and is not design authority."),
            "basement_exterior_wall_thickness": item(0.20, "user input", "basement_wall.thickness", "USER_PROJECT_REQUIREMENT"),
            "basement_geometric_wall_height": item(2.40, Path(__file__),
                "ground elevation - basement elevation", "DERIVED_GEOMETRIC_CONSTRAINT",
                "This is not classified as clear height."),
            "stair_core_location": item(None, "user input", "core candidate location", "MISSING",
                "Maximum dimensions are authoritative; actual footprint/location remains a design variable."),
            "ramp_width": item(3.5, "user input", "ramp.clear_width", "USER_PROJECT_REQUIREMENT"),
            "ramp_run": item(requirements["ramp"]["derived_minimum_run"], Path(__file__),
                "abs(delta_z) / maximum_longitudinal_slope", "DERIVED_GEOMETRIC_CONSTRAINT"),
            "ramp_slope": item(0.15, "user input", "ramp.maximum_longitudinal_slope", "USER_PROJECT_REQUIREMENT"),
            "ramp_start_elevation": item(0.0, "user input", "levels.ground", "USER_PROJECT_REQUIREMENT"),
            "ramp_end_elevation": item(-2.4, "user input", "levels.ramp_arrival", "USER_PROJECT_REQUIREMENT"),
            "basement_elevation": item(-2.4, "user input", "levels.basement", "USER_PROJECT_REQUIREMENT"),
            "vehicle_opening": item(None, PREVIOUS / "acceptance_summary.json", "vehicle access resolution", "MISSING"),
            "parking_stall_dimensions": item([2.5, 5.0], "user input", "parking", "USER_PROJECT_REQUIREMENT"),
            "parking_count": item(2, "user input", "parking.minimum_count", "USER_PROJECT_REQUIREMENT"),
            "parking_aisle": item(None, PREVIOUS / "acceptance_summary.json", "parking topology", "MISSING"),
            "parking_aisle_width": item(5.0, "user input", "parking.aisle_width", "USER_PROJECT_REQUIREMENT"),
            "minimum_turning_radius": item(5.0, "user input", "parking.minimum_turning_radius", "USER_PROJECT_REQUIREMENT"),
            "maneuvering_envelope": item(None, PREVIOUS / "acceptance_summary.json", "parking arrival", "MISSING"),
            "slab_opening_ramp_void": item(None, PREVIOUS / "acceptance_summary.json", "ramp clearance", "MISSING"),
            "pedestrian_connection": item(None, PREVIOUS / "acceptance_summary.json", "parking pedestrian connection", "MISSING"),
            "elevator_requirement": item(True, "user input", "core.elevator_required", "USER_PROJECT_REQUIREMENT"),
            "separation_joint": item([0.0, 0.1, 0.1, 0.1], "user input",
                "per-edge clear distance to outer wall face", "USER_PROJECT_REQUIREMENT"),
        },
        "unresolved_requirements": missing,
        "candidate_generation": {
            "generated": 0,
            "rejected": 0,
            "feasible": 0,
            "selected_candidate": None,
            "status": "not_started_due_to_missing_core_and_site_inventory_requirements",
            "unresolved_evidence": missing,
        },
        "basement_design": {
            "buildable_envelope": envelope.get("buildable_boundary"),
            "buildable_envelope_area": envelope.get("buildable_area"),
            "maximum_geometric_coverage_percent": (
                envelope.get("buildable_area") / site["area"] * 100.0
                if envelope.get("status") == "resolved" else None
            ),
            "physical_wall_footprint": {
                "outer_face": envelope.get("buildable_boundary"),
                "centerline": wall_centerline.get("buildable_boundary"),
                "inner_face": wall_inner_face.get("buildable_boundary"),
                "thickness": 0.20,
                "geometric_height": 2.40,
                "geometry_status": "resolved_boundary_evidence",
            },
            "ramp": None,
            "ramp_void": None,
            "parking_stalls": [],
            "maneuvering": None,
            "pedestrian_connection": None,
            "core_location": None,
            "geometry_status": "pending_requirement",
        },
        "automated_geometry_pass": False,
        "human_visual_acceptance": "pending",
        "artifacts": {
            "plan": None,
            "model_3d": None,
            "reason": "No resolved geometry may be visualized as a Basement V2 design.",
        },
    }
    output = ROOT / "exports" / "DEFAULT" / (
        "parcel2_basement_v2_requirements_audit_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    )
    output.mkdir(parents=True, exist_ok=False)
    report = output / "PARCEL2_BASEMENT_V2_REQUIREMENTS_AUDIT.json"
    report.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "report": str(report),
                      "status": audit["status"], "candidate_generation": audit["candidate_generation"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
