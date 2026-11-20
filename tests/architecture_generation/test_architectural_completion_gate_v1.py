from core.architecture.reasoning.architectural_completion_gate_v1 import ArchitecturalCompletionGateV1
from tests.architecture_generation.test_complete_architecture_vehicle_access_acceptance import _generate_and_export


def test_completion_gate_passes_when_final_runtime_spatial_quality_is_proven():
    _, resolved, _ = _generate_and_export(
        "north_road", "north", "direct_at_grade", -2.4, 0.0, "completion_gate_north"
    )
    gate = resolved["architectural_geometry"]["architecture_completion_gate"]
    assert gate["architecture_complete"] is True
    assert gate["critical_failures"] == []
    assert gate["checks"]["vehicle_entrance_and_driveway"]["status"] == "passed"
    assert gate["checks"]["parking_arrival_turning_stalls"]["status"] == "passed"


def test_completion_gate_accepts_a_fully_resolved_architectural_contract():
    geometry = {
        "project_requirements": {
            "vertical_transport": {"stairs": [{"id": "S1", "required": True}]},
            "vehicle_access": {"entrances": [{"access_id": "V1"}]},
            "parking_requirements": [{"required": True}],
        },
        "openings": [{"id": "D1", "geometry_status": "resolved", "geometry_generation_allowed": True, "host_wall_id": "W1"},
                     {"id": "V1", "type": "vehicle_entrance", "geometry_status": "resolved", "geometry_generation_allowed": True, "host_wall_id": "W2"}],
        "physical_walls": [{"wall_id": "W1", "outer_face_clearance_status": "resolved"}],
        "vertical_geometry": [{"type": "stair_geometry", "stair_id": "S1", "geometry_status": "resolved"},
                              {"type": "vehicle_ramp", "geometry_status": "resolved"}],
        "slab_openings": [{"type": "stair_slab_opening", "geometry_status": "resolved"},
                          {"type": "vehicle_ramp_clearance_slab_opening", "geometry_status": "resolved"}],
        "ramp_clearance": {"geometry_status": "resolved"},
        "site_geometry": {
            "vehicle_access": {"entrance": {"entrance_status": "resolved"},
                               "driveway": {"geometry_status": "resolved"}},
            "parking_arrival": {"geometry_status": "resolved"},
            "parking_layout": {"geometry_status": "resolved", "parking_stalls": [{"aisle_access": True}]},
        },
        "spatial_quality_gate": {"status": "passed"},
        "cad_drawing_contract": {"geometry_status": "resolved"},
        "architectural_section": {"geometry_status": "resolved"},
    }
    gate = ArchitecturalCompletionGateV1().evaluate(geometry)
    assert gate["architecture_complete"] is True
    assert gate["critical_failures"] == []


def test_south_completion_gate_confirms_ramp_headroom_void_and_proven_rooms():
    _, resolved, _ = _generate_and_export(
        "south_road", "south", "vehicle_ramp", 0.0, 16.0, "completion_gate_south"
    )
    gate = resolved["architectural_geometry"]["architecture_completion_gate"]
    assert gate["checks"]["ramp_headroom"]["status"] == "passed"
    assert gate["checks"]["ramp_slab_void"]["status"] == "passed"
    assert gate["architecture_complete"] is True
