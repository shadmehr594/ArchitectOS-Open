import pytest

from core.architecture.geometry.architectural_ramp_clearance_resolver_v1 import (
    ArchitecturalRampClearanceResolverV1,
)
from tests.architecture_generation.test_complete_architecture_vehicle_access_acceptance import (
    _generate_and_export,
)


def _ramp():
    return {
        "access_id": "V1", "ramp_id": "R1", "width": 3.5,
        "polygon": [[-1.75, 0], [-1.75, 16], [1.75, 16], [1.75, 0]],
        "centerline_3d": [[0, 0, 0], [0, 16, -2.4]],
        "start_z": 0.0, "end_z": -2.4, "slope": 0.15,
    }


def _slabs():
    return [{"slab_id": "F1-S", "floor": "F1", "elevation": 0.0,
             "footprint": {"points": [[-5, 2], [5, 2], [5, 20], [-5, 20]]}}]


def test_formal_headroom_resolves_clearance_envelope_and_real_slab_void():
    result = ArchitecturalRampClearanceResolverV1().resolve(
        _ramp(), _slabs(), {"access_id": "V1", "required_headroom": 2.2,
                            "source": "project", "evidence_status": "authoritative"})
    assert result["geometry_status"] == "resolved"
    assert result["clearance_start"] == [0.0, 0.0, 0.0, 2.2]
    assert result["clearance_end"] == pytest.approx([0.0, 16.0, -2.4, -0.2])
    assert result["open_to_sky_zone"]
    assert result["affected_floor"] == "F1"
    assert result["slab_opening"]["polygon"] == result["slab_opening_polygon"]
    assert result["protected_zone"]["structural_exclusion_contract"] is True


def test_missing_headroom_remains_pending_without_void():
    result = ArchitecturalRampClearanceResolverV1().resolve(
        _ramp(), _slabs(), {"access_id": "V1", "evidence_status": "authoritative"})
    assert result["geometry_status"] == "pending"
    assert result["slab_opening_polygon"] is None
    assert "required_headroom" in result["unresolved_evidence"]


def test_south_runtime_resolves_clearance_but_north_creates_no_ramp_void():
    _, south, _ = _generate_and_export("south_road", "south", "vehicle_ramp", 0.0, 16.0,
                                       "ramp_clearance_south")
    assert south["ramp_clearance_status"] == "resolved"
    assert south["ramp_clearance"]["slab_opening"]["geometry_status"] == "resolved"
    assert south["architectural_geometry"]["architectural_protected_zones"]
    _, north, _ = _generate_and_export("north_road", "north", "direct_at_grade", -2.4, 0.0,
                                       "ramp_clearance_north")
    assert north["ramp_clearance_status"] == "not_required"
    assert not any(item.get("type") == "vehicle_ramp_clearance_slab_opening"
                   for item in north["architectural_geometry"].get("slab_openings", []))
