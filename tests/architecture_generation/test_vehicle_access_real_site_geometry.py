import pytest

from core.architecture.geometry.vehicle_access_geometry_resolver_v1 import (
    VehicleAccessGeometryResolverV1,
)
from core.intelligence.architectural_intelligence_orchestrator import (
    ArchitecturalIntelligenceOrchestrator,
)
from core.geometry.ramp_3d_geometry_engine import Ramp3DGeometryEngine


def _geometry():
    return {
        "project_requirements": {"vehicle_access": {"entrances": [
            {"access_id": "south_road", "served_level": "basement", "clear_width": 3.5,
             "clear_height": 2.4, "opening_role": "basement_vehicle_entrance",
             "source": "legacy_fixture_migration", "evidence_status": "authoritative"},
            {"access_id": "north_rear_lane", "served_level": "basement", "clear_width": 3.5,
             "clear_height": 2.4, "opening_role": "basement_vehicle_entrance",
             "source": "legacy_fixture_migration", "evidence_status": "authoritative"},
        ]}},
        "physical_walls": [
            {"wall_id": "B-S", "floor": "basement", "start": [0, 0], "end": [20, 0],
             "is_exterior": True, "thickness": 0.30},
            {"wall_id": "B-E", "floor": "basement", "start": [20, 0], "end": [20, 30],
             "is_exterior": True, "thickness": 0.30},
            {"wall_id": "B-N", "floor": "basement", "start": [20, 30], "end": [0, 30],
             "is_exterior": True, "thickness": 0.30},
            {"wall_id": "B-W", "floor": "basement", "start": [0, 30], "end": [0, 0],
             "is_exterior": True, "thickness": 0.30},
        ],
        "site_geometry": {
            "parcel_boundary": [[0, 0], [20, 0], [20, 30], [0, 30]],
            "parcel_edges": [
                {"id": "south_edge", "access_id": "south_road", "edge_index": 0,
                 "start": [0, 0], "end": [20, 0], "confirmed": True},
                {"id": "north_edge", "access_id": "north_rear_lane", "edge_index": 2,
                 "start": [20, 30], "end": [0, 30], "confirmed": True},
            ],
            "parking_access_points": {
                "basement": [10, 20],
            },
            "conflict_zones": [],
        },
        "vertical_geometry": [],
    }


def _selection(access_id, mode, access_z, target_z, run=0.0):
    interval = ([[8.25, 0.0], [11.75, 0.0]] if access_id == "south_road"
                else [[11.75, 30.0], [8.25, 30.0]])
    return {
        "status": "resolved",
        "selected_system": "vehicle_ramp",
        "selected_access_id": access_id,
        "selected_access_candidate": {
            "access_id": access_id,
            "access_mode": mode,
            "access_elevation": access_z,
            "target_elevation": target_z,
            "target_level": "basement",
            "delta_z": target_z - access_z,
            "absolute_level_difference": abs(target_z - access_z),
            "required_run": run,
            "ramp_geometry_required": mode == "vehicle_ramp",
            "site_fit": True,
            "entrance_interval": interval,
            "source": "user_explicit",
        },
        "geometry_generation_allowed": True,
        "ramp_geometry_allowed": mode == "vehicle_ramp",
        "driveway_geometry_allowed": True,
        "evidence_used": ["verified_vehicle_access_edge"],
    }


def test_direct_at_grade_generates_driveway_without_ramp_and_survives_geometry():
    result = VehicleAccessGeometryResolverV1().resolve(
        _selection("north_rear_lane", "direct_at_grade", -2.5, -2.5),
        _geometry(),
        {"clear_width": 3.5},
    )
    assert result["status"] == "resolved"
    assert result["selected_access_geometry"]["parcel_edge_id"] == "north_edge"
    assert result["driveway"]["type"] == "vehicle_driveway"
    assert result["driveway"]["start_z"] == pytest.approx(-2.5)
    assert result["driveway"]["end_z"] == pytest.approx(-2.5)
    assert result["ramp"] is None
    geometry = result["architectural_geometry"]
    assert geometry["site_geometry"]["vehicle_access"]["driveway"] == result["driveway"]
    assert not any(item.get("type") == "vehicle_ramp" for item in geometry["vertical_geometry"])


def test_resolved_south_ramp_uses_real_edge_and_distance_based_z():
    geometry = _geometry()
    geometry["site_geometry"]["parking_access_points"]["basement"] = [10, 16.6666667]
    result = VehicleAccessGeometryResolverV1().resolve(
        _selection("south_road", "vehicle_ramp", 0.0, -2.5, 16.6666667),
        geometry,
        {"clear_width": 3.5},
    )
    assert result["status"] == "resolved"
    entrance = result["entrance"]
    assert entrance["entrance_center"][1] == pytest.approx(0.0)
    assert entrance["entrance_center"] != [0, 0]
    ramp = result["ramp"]
    assert ramp["required_run"] == pytest.approx(16.6666667)
    assert ramp["entry_point"] == entrance["entrance_center"]
    assert ramp["start_z"] == pytest.approx(0.0)
    assert ramp["end_z"] == pytest.approx(-2.5)
    centerline_z = [point[2] for point in ramp["centerline_3d"]]
    assert centerline_z[0] == pytest.approx(0.0)
    assert centerline_z[-1] == pytest.approx(-2.5)
    assert all(a >= b for a, b in zip(centerline_z, centerline_z[1:]))
    assert [point[2] for point in ramp["geometry"]] == pytest.approx(
        [0.0, -2.5, -2.5, 0.0]
    )
    assert result["architectural_geometry"]["vertical_geometry"][-1] == ramp
    assert ramp["surface"]["geometry_status"] == "resolved"
    assert ramp["arrival_interface"]["point"] == pytest.approx([10, 16.6666667])


def test_unknown_access_geometry_fails_closed_without_origin_fallback():
    result = VehicleAccessGeometryResolverV1().resolve(
        _selection("unknown_access", "direct_at_grade", -2.5, -2.5),
        _geometry(),
        {"clear_width": 3.5},
    )
    assert result["status"] == "selected_access_geometry_unresolved"
    assert result["geometry_generation_allowed"] is False
    assert result["driveway_geometry_allowed"] is False
    assert result["ramp_geometry_allowed"] is False
    assert result["driveway"] is None
    assert result["ramp"] is None


def test_edge_identity_wins_independently_of_side_name():
    geometry = _geometry()
    selection = _selection("south_road", "direct_at_grade", -2.5, -2.5)
    selection["selected_access_candidate"]["side"] = "north"
    result = VehicleAccessGeometryResolverV1().resolve(
        selection, geometry, {"clear_width": 3.5}
    )
    assert result["selected_access_geometry"]["parcel_edge_id"] == "south_edge"


def test_protected_conflict_is_never_silently_ignored():
    geometry = _geometry()
    geometry["site_geometry"]["conflict_zones"] = [
        {"id": "core", "type": "elevator_core", "protected_zone": True,
         "bbox": [8, 0, 12, 8]}
    ]
    result = VehicleAccessGeometryResolverV1().resolve(
        _selection("south_road", "direct_at_grade", -2.5, -2.5),
        geometry,
        {"clear_width": 12.0},
    )
    assert result["conflict_validation"]["status"] in {
        "conflict_detected", "conflict_check_pending"
    }
    assert result["geometry_generation_allowed"] is False


def test_missing_conflict_evidence_remains_pending():
    geometry = _geometry()
    del geometry["site_geometry"]["conflict_zones"]
    result = VehicleAccessGeometryResolverV1().resolve(
        _selection("north_rear_lane", "direct_at_grade", -2.5, -2.5),
        geometry,
        {"clear_width": 3.5},
    )
    assert result["conflict_validation"]["status"] == "conflict_check_pending"
    assert result["geometry_generation_allowed"] is False


def test_real_orchestrator_attaches_driveway_to_authoritative_geometry():
    context = {
        "requirements": ["parking"], "floors": [],
        "site": {"area": 600.0, "bbox": {"width": 20.0, "height": 30.0}},
        "site_constraints": {"access_elevations": [
            {"id": "north_rear_lane", "side": "north", "type": "rear_lane",
             "elevation": -2.5, "vehicle_access": True, "source": "user_explicit",
             "access_edge_status": "confirmed",
             "entrance_interval": [[11.75, 30.0], [8.25, 30.0]],
             "access_point": [10.0, 30.0]}
        ]},
        "parking": {"level": "basement", "elevation": -2.5},
        "allowable_vehicle_ramp_slope_percent": 15.0,
        "minimum_vehicle_ramp_width": 3.5,
        "vehicle_turning_radius": 5.5,
        "architectural_geometry": _geometry(),
    }
    result = ArchitecturalIntelligenceOrchestrator().analyze(context)
    assert result["vehicle_access_geometry"]["status"] == "resolved"
    assert result["architectural_geometry"]["site_geometry"]["vehicle_access"]["driveway"]
    assert result["vehicle_access_geometry"]["ramp"] is None


def test_l_shaped_ramp_z_follows_centerline_distance_not_vertex_index():
    result = Ramp3DGeometryEngine().generate(
        {
            "shape": "L",
            "centerline": [[0, 0], [10, 0], [10, 10]],
            "polygon": [[0, 1], [10, 1], [9, 10], [11, 10], [10, -1], [0, -1]],
        },
        {"start_z": 0.0, "end_z": -2.5, "width": 2.0},
    )
    assert [point[2] for point in result["centerline_3d"]] == pytest.approx(
        [0.0, -1.25, -2.5]
    )
    # Both vertices at the end landing resolve to the same end elevation;
    # vertex-list order no longer controls Z.
    assert result["geometry"][2][2] == pytest.approx(-2.5)
    assert result["geometry"][3][2] == pytest.approx(-2.5)
