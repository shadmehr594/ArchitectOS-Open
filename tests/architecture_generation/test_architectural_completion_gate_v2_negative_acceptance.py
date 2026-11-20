from copy import deepcopy

import pytest

from core.architecture.reasoning.architectural_completion_gate_v2 import ArchitecturalCompletionGateV2
from core.architecture.reasoning.architectural_spatial_quality_gate_v2 import ArchitecturalSpatialQualityGateV2
from tests.architecture_generation.test_complete_architecture_vehicle_access_acceptance import _generate_and_export


@pytest.fixture(scope="module")
def completed_geometry():
    _, _, result = _generate_and_export(
        "south_road", "south", "vehicle_ramp", 0.0, 16.0,
        "final_completion_negative_base",
    )
    geometry = result["geometry"]
    assert geometry["architecture_completion_gate"]["architecture_complete"] is True
    return geometry


def evaluate(geometry):
    geometry["spatial_quality_gate"] = ArchitecturalSpatialQualityGateV2().evaluate(
        geometry, geometry["project_requirements"]["spatial_quality_requirements"]
    )
    return ArchitecturalCompletionGateV2().evaluate(geometry)


def first_interior_door(geometry):
    return next(o for o in geometry["openings"] if o.get("type") == "door" and o.get("connection_id"))


def test_removing_required_interior_door_closes_completion(completed_geometry):
    geometry = deepcopy(completed_geometry); door = first_interior_door(geometry)
    geometry["openings"] = [o for o in geometry["openings"] if o.get("opening_id") != door["opening_id"]]
    assert evaluate(geometry)["architecture_complete"] is False


def test_removing_stair_interface_closes_completion(completed_geometry):
    geometry = deepcopy(completed_geometry); geometry["vertical_interfaces"].pop()
    assert evaluate(geometry)["architecture_complete"] is False


def test_removing_parking_pedestrian_chain_closes_completion(completed_geometry):
    geometry = deepcopy(completed_geometry); geometry["site_geometry"]["parking_pedestrian_connection"] = {}
    assert evaluate(geometry)["architecture_complete"] is False


def test_unresolving_required_connection_closes_completion(completed_geometry):
    geometry = deepcopy(completed_geometry); connection = geometry["spatial_connection_contract"]["connections"][0]
    connection["geometry_status"] = "unresolved"; connection["physical_connection_status"] = "pending"
    assert evaluate(geometry)["architecture_complete"] is False


def test_removing_wall_interruption_closes_completion(completed_geometry):
    geometry = deepcopy(completed_geometry); door = first_interior_door(geometry)
    wall = next(w for w in geometry["physical_walls"] if w.get("wall_id") == door["host_wall_id"])
    wall["physical_openings"] = [o for o in wall.get("physical_openings", []) if o.get("opening_id") != door["opening_id"]]
    assert evaluate(geometry)["architecture_complete"] is False


def test_high_score_and_manual_override_cannot_bypass_failure(completed_geometry):
    geometry = deepcopy(completed_geometry); geometry["site_geometry"]["parking_pedestrian_connection"] = {}
    geometry["spatial_quality_gate"] = ArchitecturalSpatialQualityGateV2().evaluate(
        geometry, geometry["project_requirements"]["spatial_quality_requirements"]
    )
    geometry["spatial_quality_gate"]["quality_score"] = 100.0
    geometry["architecture_complete"] = True
    result = ArchitecturalCompletionGateV2().evaluate(geometry)
    assert result["architecture_complete"] is False and result["manual_override_allowed"] is False


def test_unresolved_enforcement_never_passes(completed_geometry):
    geometry = deepcopy(completed_geometry)
    geometry["spatial_quality_gate"] = ArchitecturalSpatialQualityGateV2().evaluate(geometry, {})
    assert ArchitecturalCompletionGateV2().evaluate(geometry)["architecture_complete"] is False


def test_door_to_nowhere_closes_completion(completed_geometry):
    geometry = deepcopy(completed_geometry); door = first_interior_door(geometry)
    door["connects_from"] = door["from_space_id"] = None; door["connects_to"] = door["to_space_id"] = None
    assert evaluate(geometry)["architecture_complete"] is False


def test_invalid_exterior_window_closes_completion(completed_geometry):
    geometry = deepcopy(completed_geometry); window = deepcopy(first_interior_door(geometry))
    window.update({"opening_id": "INVALID-WINDOW", "id": "INVALID-WINDOW", "type": "window",
                   "served_space_id": "living", "exterior_host_status": "pending"})
    wall = next(w for w in geometry["physical_walls"] if w.get("wall_id") == window["host_wall_id"])
    wall.setdefault("physical_openings", []).append(deepcopy(window)); geometry["openings"].append(window)
    assert evaluate(geometry)["architecture_complete"] is False
