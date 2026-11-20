"""Generate real Parcel-2 SOUTH diagnostic artifacts, preserving fail-closed state."""

from datetime import datetime
import json
from pathlib import Path

from core.architecture.brain.architectural_brain import ArchitecturalBrain
from core.architecture.reasoning.vehicle_site_access_candidate_geometry_design_reasoner_v1 import VehicleSiteAccessCandidateGeometryDesignReasonerV1
from core.architecture.reasoning.basement_vehicle_architectural_acceptance_v2 import BasementVehicleArchitecturalAcceptanceV2
from core.architecture.visualization.architectural_geometry_preview_v1 import ArchitecturalGeometryPreviewV1
from core.export.dwg.dwg_writer import DWGWriter
from core.export.dwg.dwg_converter import DWGConverter
from tests.architecture_generation.test_basement_ramp_parcel2_acceptance_v2 import _real_parcel2_intent


def main():
    model = ArchitecturalBrain().design(_real_parcel2_intent()).to_dict()
    intelligence = model["architectural_intelligence"]
    geometry = intelligence["architectural_geometry"]
    parcel = model["site_analysis"]["building_strategy"]["parcel_boundary"]
    basement = next(item for item in geometry["floor_geometry"] if item["floor"] == "basement")
    stair = next(item for item in geometry["vertical_geometry"] if item.get("type") == "stair_geometry")
    site = {
        "parcel_boundary": parcel,
        "parcel_edges": [{"id":"parcel2-road-edge-0","access_id":"parcel2-south-road",
            "edge_index":0,"start":parcel[0],"end":parcel[1],"confirmed":True}],
        "conflict_inventory_complete": True,
        "conflict_zones": [{"id":"stair-core","type":"stair_core",
            "polygon":stair["protected_zone"]["points"]}],
        "parking_target_regions": {"basement":{"polygon":basement["parcel_envelope"]["points"],
            "source":"resolved_basement_usable_footprint"}},
    }
    feasibility = {"ramp":{"minimum_width":3.5,"access_candidates":[{
        "status":"feasible","access_id":"parcel2-south-road","access_edge_reference":"parcel2-road-edge-0",
        "target_level":"basement","required_run":16.0,"ramp_geometry_required":True,
        "building_entry_allowed":True,"parking_target_reference":"basement",
        "parking_target_source":"resolved_basement_usable_footprint",
        "ramp_transition_length":1.0,"ramp_transition_width":3.5,
    }]}}
    design = VehicleSiteAccessCandidateGeometryDesignReasonerV1().design(
        site, feasibility, {"selected_system":"vehicle_ramp"}
    )
    acceptance = BasementVehicleArchitecturalAcceptanceV2().evaluate(geometry, {})
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output = Path("exports") / "DEFAULT" / f"basement_ramp_parking_v2_south_{run_id}"
    output.mkdir(parents=True, exist_ok=False)
    geometry["site_geometry"]["parcel_boundary"] = parcel
    dxf = output / "ArchitectOS_Project_ARCHITECTURE_ONLY.dxf"
    DWGWriter().export(geometry, {}, str(dxf))
    dwg = output / "ArchitectOS_Project.dwg"
    dwg_result = DWGConverter().convert(str(dxf), str(dwg))
    candidates = design["access_candidates"]
    preview = ArchitecturalGeometryPreviewV1()
    preview.plan(geometry, str(output / "PLAN_PREVIEW.png"), candidates)
    preview.model(geometry, str(output / "MODEL_PREVIEW.png"), candidates)
    (output / "MODEL_GEOMETRY.json").write_text(json.dumps({
        "physical_walls": geometry.get("physical_walls", []), "slabs": geometry.get("slabs", []),
        "vertical_geometry": geometry.get("vertical_geometry", []), "vehicle_access_design": design,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"source_parcel":"tests/data/real_site/parcel_2_source.dxf#parcel=2",
        "vehicle_access_design":design,"acceptance":acceptance,"human_visual_acceptance":"pending",
        "dwg":dwg_result,"artifacts":{"dxf":str(dxf.resolve()),"dwg":str(dwg.resolve()),
        "plan_preview":str((output/'PLAN_PREVIEW.png').resolve()),
        "model_preview":str((output/'MODEL_PREVIEW.png').resolve()),
        "model_geometry":str((output/'MODEL_GEOMETRY.json').resolve())}}
    (output / "acceptance_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output":str(output.resolve()),"acceptance":acceptance,"dwg":dwg_result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
