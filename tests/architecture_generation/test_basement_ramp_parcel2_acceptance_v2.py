from copy import deepcopy
from math import hypot

import pytest

from core.cad.cad_import_engine import CADImportEngine
from core.architecture.brain.architectural_brain import ArchitecturalBrain
from core.architecture.reasoning.vehicle_site_access_candidate_geometry_design_reasoner_v1 import (
    VehicleSiteAccessCandidateGeometryDesignReasonerV1,
)
from core.architecture.reasoning.basement_vehicle_architectural_acceptance_v2 import (
    BasementVehicleArchitecturalAcceptanceV2,
)
from core.geometry.ramp_3d_geometry_engine import Ramp3DGeometryEngine
from tests.architecture_generation.test_complete_architecture_vehicle_access_acceptance import (
    _architectural_intent,
)


def _real_parcel2_intent():
    cad = CADImportEngine().load(
        {"file_object": r"tests\data\real_site\parcel_2_source.dxf"},
        target_parcel=2,
    )
    intent = _architectural_intent(0)
    intent["site"] = deepcopy(cad["site"])
    intent["site"]["building_height"] = 3.6
    intent["site"]["neighbors"] = {}
    # Compact project program is dimensional evidence; placement remains the
    # responsibility of the real parcel/layout pipeline.
    dimensions = {
        "basement": (9.0, 19.0), "entrance": (1.8, 2.0),
        "corridor": (1.5, 5.0), "living": (3.6, 3.8),
        "dining": (2.8, 3.0), "kitchen": (2.8, 3.0),
        "guest_wc": (1.5, 1.8),
    }
    for space in intent["spaces"]:
        width, depth = dimensions[space["name"]]
        space["resolved_dimensions"] = {
            "width": width, "depth": depth, "area": width * depth,
        }
    # The previous rectangular-site parking coordinates are deliberately
    # removed. Parcel-2 acceptance may only continue after a target is derived
    # or supplied in the real-parcel coordinate system.
    parking = intent["parking_requirements"][0]
    for key in ("parking_target_point", "aisle_centerline"):
        parking.pop(key, None)
    parking["parking_target_source"] = None
    return intent


def test_real_parcel2_reaches_architectural_geometry_without_rectangular_site_fixture():
    model = ArchitecturalBrain().design(_real_parcel2_intent()).to_dict()
    site = model["site_analysis"]
    geometry = model["architectural_intelligence"]["architectural_geometry"]
    assert site["building_strategy"]["parcel_area"] == pytest.approx(200.0001220703125)
    assert site["building_strategy"]["parcel_boundary"][0] == pytest.approx([9.495348, 22.127313])
    assert model["architectural_intelligence"]["geometry_intent"]["parcel_placement"]["status"] == "resolved"
    assert geometry["physical_walls"]
    assert geometry["slabs"]


def test_real_parcel2_rejects_ramp_candidates_that_cross_resolved_stair_core():
    model = ArchitecturalBrain().design(_real_parcel2_intent()).to_dict()
    geometry = model["architectural_intelligence"]["architectural_geometry"]
    parcel = model["site_analysis"]["building_strategy"]["parcel_boundary"]
    basement = next(item for item in geometry["floor_geometry"] if item["floor"] == "basement")
    stair = next(item for item in geometry["vertical_geometry"] if item.get("type") == "stair_geometry")
    site = {
        "parcel_boundary": parcel,
        "parcel_edges": [{
            "id": "parcel2-road-edge-0", "access_id": "parcel2-south-road",
            "edge_index": 0, "start": parcel[0], "end": parcel[1], "confirmed": True,
        }],
        "conflict_inventory_complete": True,
        "conflict_zones": [{
            "id": "stair-core", "type": "stair_core",
            "polygon": stair["protected_zone"]["points"],
        }],
        "parking_target_regions": {
            "basement": {
                "polygon": basement["parcel_envelope"]["points"],
                "source": "resolved_basement_usable_footprint",
            }
        },
    }
    feasibility = {"ramp": {
        "minimum_width": 3.5,
        "access_candidates": [{
            "status": "feasible", "access_id": "parcel2-south-road",
            "access_edge_reference": "parcel2-road-edge-0",
            "target_level": "basement", "required_run": 16.0,
            "ramp_geometry_required": True, "building_entry_allowed": True,
            "parking_target_reference": "basement",
            "parking_target_source": "resolved_basement_usable_footprint",
            "ramp_transition_length": 1.0, "ramp_transition_width": 3.5,
        }],
    }}
    result = VehicleSiteAccessCandidateGeometryDesignReasonerV1().design(
        site, feasibility, {"selected_system": "vehicle_ramp"},
    )
    assert not [item for item in result["access_candidates"]
                if item.get("geometry_status") == "resolved_candidate"]
    assert result["selection_status"] == "pending"
    assert {item.get("selection_reason") for item in result["access_candidates"]} == {
        "driveway_corridor_intersects_conflict_zone"
    }


def test_ramp_surface_is_real_and_acceptance_cannot_pass_on_centerline_only():
    ramp = Ramp3DGeometryEngine().generate(
        {"shape": "straight", "centerline": [[0, 0], [0, 16]],
         "polygon": [[-1.75, 0], [-1.75, 16], [1.75, 16], [1.75, 0]]},
        {"width": 3.5, "start_z": 0.0, "end_z": -2.4, "slope": 0.15},
    )
    assert ramp["surface"]["geometry_status"] == "resolved"
    assert len(ramp["surface"]["vertices"]) == 4
    assert len(ramp["surface"]["faces"]) == 2
    geometry = {"floor_geometry": [{"floor": "basement"}, {"floor": "F1"}]}
    verdict = BasementVehicleArchitecturalAcceptanceV2().evaluate(
        geometry, {"status": "resolved", "ramp": {"centerline_3d": ramp["centerline_3d"]}}
    )
    assert verdict["automated_geometry_pass"] is False
    assert verdict["human_visual_acceptance"] == "pending"
    assert "physical_ramp_surface" in verdict["failed_checks"]


def test_mismatched_ramp_target_fails_closed_before_physical_publication():
    from core.architecture.geometry.vehicle_access_geometry_resolver_v1 import VehicleAccessGeometryResolverV1
    geometry = {
        "project_requirements": {"vehicle_access": {"entrances": [{
            "access_id": "a", "served_level": "basement", "clear_width": 3.5,
            "clear_height": 2.4, "evidence_status": "authoritative",
        }]}},
        "physical_walls": [], "vertical_geometry": [],
        "site_geometry": {"parcel_boundary": [[0,0],[10,0],[10,20],[0,20]],
            "parcel_edges": [{"id":"e","access_id":"a","edge_index":0,"start":[0,0],"end":[10,0],"confirmed":True}],
            "parking_access_points":{"basement":[5,10]}, "conflict_zones":[]},
    }
    selection = {"status":"resolved","selected_access_id":"a","geometry_generation_allowed":True,
        "ramp_geometry_allowed":True,"selected_access_candidate":{"access_id":"a","target_level":"basement",
        "access_mode":"vehicle_ramp","access_elevation":0.0,"target_elevation":-2.4,"required_run":16.0,
        "site_fit":True,"entrance_interval":[[3.25,0],[6.75,0]]}}
    result = VehicleAccessGeometryResolverV1().resolve(selection, geometry, {"clear_width":3.5})
    assert result["status"] == "ramp_geometry_unresolved"
    assert result["ramp"] is None
