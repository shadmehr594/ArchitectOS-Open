import os

import ezdxf
import ifcopenshell
import pytest

from core.architecture.geometry.vehicle_access_geometry_resolver_v1 import (
    VehicleAccessGeometryResolverV1,
)
from core.integration.design_bim_bridge import DesignBIMBridge


LEVELS = [
    {"name": "basement", "bottom": -2.5, "top": 0.0, "height": 2.5},
    {"name": "ground", "bottom": 0.0, "top": 3.2, "height": 3.2},
]


def _base_geometry():
    return {
        "version": "2.1",
        "spaces": [], "openings": [], "slabs": [],
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
             "bottom": -2.5, "top": 0.0, "height": 2.5, "is_exterior": True, "thickness": 0.30},
            {"wall_id": "B-N", "floor": "basement", "start": [20, 30], "end": [0, 30],
             "bottom": -2.5, "top": 0.0, "height": 2.5, "is_exterior": True, "thickness": 0.30},
        ],
        "floor_geometry": [
            {"floor": item["name"], "bottom": item["bottom"], "top": item["top"],
             "height": item["height"], "footprint": {"points": [[0, 0], [20, 0], [20, 30], [0, 30]]}}
            for item in LEVELS
        ],
        "vertical_geometry": [],
        "site_geometry": {
            "parcel_boundary": [[0, 0], [20, 0], [20, 30], [0, 30]],
            "parcel_edges": [
                {"id": "south_edge", "access_id": "south_road", "edge_index": 0,
                 "start": [0, 0], "end": [20, 0], "confirmed": True},
                {"id": "north_edge", "access_id": "north_rear_lane", "edge_index": 2,
                 "start": [20, 30], "end": [0, 30], "confirmed": True},
            ],
            "parking_access_points": {"basement": [10, 20]},
            "conflict_zones": [],
        },
    }


def _selection(access_id, mode, access_z, run):
    return {
        "status": "resolved", "selected_system": "vehicle_ramp",
        "selected_access_id": access_id,
        "selected_access_candidate": {
            "access_id": access_id, "access_mode": mode,
            "access_elevation": access_z, "target_elevation": -2.5,
            "target_level": "basement", "delta_z": -2.5 - access_z,
            "absolute_level_difference": abs(-2.5 - access_z),
            "required_run": run, "ramp_geometry_required": mode == "vehicle_ramp",
            "site_fit": True, "source": "user_explicit",
        },
        "geometry_generation_allowed": True,
        "driveway_geometry_allowed": True,
        "ramp_geometry_allowed": mode == "vehicle_ramp",
    }


def _export(access_id, mode, access_z, run, label):
    resolved = VehicleAccessGeometryResolverV1().resolve(
        _selection(access_id, mode, access_z, run), _base_geometry(),
        {"slope": 0.15},
    )
    geometry = resolved["architectural_geometry"]
    result = DesignBIMBridge().run_bim({
        "architectural_geometry": geometry, "geometry": geometry,
        "vertical_section": {"levels": LEVELS, "roof_level": 3.2},
        "geometry_intent": {}, "generate_structure": False,
        "run_id": label, "export_session": "DEFAULT",
    })["bim_result"]
    assert result["exports"]["status"] == "completed"
    return resolved, result


def test_direct_at_grade_real_ifc_dxf_dwg_export():
    resolved, result = _export(
        "north_rear_lane", "direct_at_grade", -2.5, 0.0,
        "vehicle_access_export_acceptance_direct",
    )
    exports = result["exports"]
    model = ifcopenshell.open(exports["ifc"]["path"])
    assert len(model.by_type("IfcRamp")) == 0
    driveway = [item for item in model.by_type("IfcBuildingElementProxy") if item.Name == "north_rear_lane"]
    assert len(driveway) == 1 and driveway[0].Representation is not None
    doc = ezdxf.readfile(exports["cad"]["file"]["file"])
    assert len(doc.modelspace().query('*[layer=="VEHICLE_ENTRANCE"]')) >= 1
    assert len(doc.modelspace().query('*[layer=="DRIVEWAY"]')) >= 1
    assert len(doc.modelspace().query('*[layer=="VEHICLE_RAMP"]')) == 0
    assert result["geometry"]["site_accesses"][0] == resolved["driveway"] | {"target_level": "basement", "level": "basement"}
    if exports.get("dwg", {}).get("file"):
        assert os.path.getsize(exports["dwg"]["file"]) > 0


def test_ramp_required_real_ifc_dxf_dwg_export_and_z():
    resolved, result = _export(
        "south_road", "vehicle_ramp", 0.0, 16.6666667,
        "vehicle_access_export_acceptance_ramp",
    )
    exports = result["exports"]
    model = ifcopenshell.open(exports["ifc"]["path"])
    assert [(s.Name, s.Elevation) for s in model.by_type("IfcBuildingStorey")] == [
        ("Level basement", -2.5), ("Level ground", 0.0)
    ]
    assert not any(s.Name == "Level F1" for s in model.by_type("IfcBuildingStorey"))
    ramps = model.by_type("IfcRamp")
    assert len(ramps) == 1
    assert ramps[0].Representation is not None
    assert ramps[0].Tag == "south_road"
    assert ramps[0].ObjectPlacement is not None
    doc = ezdxf.readfile(exports["cad"]["file"]["file"])
    assert len(doc.modelspace().query('*[layer=="VEHICLE_ENTRANCE"]')) >= 1
    assert len(doc.modelspace().query('*[layer=="DRIVEWAY"]')) >= 1
    ramp_entities = list(doc.modelspace().query('*[layer=="VEHICLE_RAMP"]'))
    assert len(ramp_entities) >= 3
    texts = [entity.dxf.text for entity in ramp_entities if entity.dxftype() == "TEXT"]
    assert any("RAMP 15%" in text and "RUN 16.67m" in text for text in texts)
    points = [point for entity in ramp_entities if entity.dxftype() == "LWPOLYLINE" for point in entity.get_points("xy")]
    assert any(
        point[0] == pytest.approx(5.0) and point[1] == pytest.approx(0.0)
        for point in points
    )
    assert max(point[0] for point in points) > 0.0
    assert result["geometry"]["ramps"][0]["start_z"] == pytest.approx(0.0)
    assert result["geometry"]["ramps"][0]["end_z"] == pytest.approx(-2.5)
    assert result["geometry"]["vertical_geometry"][-1] == resolved["ramp"]
    if exports.get("dwg", {}).get("file"):
        with open(exports["dwg"]["file"], "rb") as handle:
            assert handle.read(2) == b"AC"
