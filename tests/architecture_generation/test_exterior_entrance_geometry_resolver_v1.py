import pytest
import ezdxf

from core.architecture.geometry.exterior_entrance_geometry_resolver_v1 import (
    ExteriorEntranceGeometryResolverV1,
)
from core.integration.design_bim_bridge import DesignBIMBridge
from core.export.dwg.dwg_writer import DWGWriter


def _geometry(*, host="W1", opening_center=(5.0, 0.0), conflicts=None):
    return {
        "physical_walls": [{
            "wall_id": "W1", "floor": "F1", "start": [0.0, 0.0],
            "end": [10.0, 0.0], "is_exterior": True,
        }],
        "openings": [{
            "id": "D1", "type": "door", "category": "main_entrance",
            "floor": "F1", "host_wall_id": host, "center": list(opening_center),
            "width": 1.4, "side": "north",
        }],
        "floor_geometry": [{
            "floor": "F1", "footprint": {
                "points": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
            },
        }],
        "site_geometry": {},
        "protected_zones": conflicts or [],
    }


def _transition(*, tread_depth=0.3, tread_count=2):
    return {
        "site_datum": {"elevation": 0.0},
        "finished_floor": {"level": "F1", "elevation": 0.4},
        "entrance_platform": {"elevation": 0.4, "depth": 1.2},
        "platform_rules": {"side_clearance": 0.3},
        "exterior_steps": {
            "start_z": 0.0, "end_z": 0.4, "total_rise": 0.4,
            "riser_count": 2, "riser_height": 0.2,
            "tread_count": tread_count, "tread_depth": tread_depth,
        },
    }


def test_main_entrance_and_exterior_normal_resolve_from_host_and_footprint():
    result = ExteriorEntranceGeometryResolverV1().resolve(_geometry(), _transition())
    entrance = result["main_entrance"]
    assert entrance["resolution_status"] == "resolved"
    assert entrance["opening_id"] == "D1"
    assert entrance["host_wall_id"] == "W1"
    assert entrance["exterior_normal"] == pytest.approx([0.0, -1.0])
    assert entrance["exterior_normal"] != [0.0, 1.0]  # side name is ignored


def test_missing_host_fails_closed_without_platform_or_step_geometry():
    result = ExteriorEntranceGeometryResolverV1().resolve(_geometry(host=None), _transition())
    assert result["main_entrance"]["resolution_status"] == "pending"
    assert result["exterior_platform_geometry"]["polygon"] is None
    assert result["entrance_steps_geometry"]["start_point"] is None
    assert result["entrance_steps_geometry"]["geometry_generation_allowed"] is False


def test_resolved_platform_is_outside_and_two_riser_contract_is_preserved():
    result = ExteriorEntranceGeometryResolverV1().resolve(_geometry(), _transition())
    platform = result["exterior_platform_geometry"]
    steps = result["entrance_steps_geometry"]
    threshold = result["entrance_threshold"]
    assert threshold["resolution_status"] == "resolved"
    assert threshold["opening_id"] == "D1"
    assert threshold["center"] == [5.0, 0.0]
    assert threshold["elevation"] == pytest.approx(0.4)
    assert platform["geometry_status"] == "resolved"
    assert platform["elevation"] == pytest.approx(0.4)
    assert all(point[1] <= 0.0 for point in platform["polygon"])
    assert steps["geometry_status"] == "resolved"
    assert steps["riser_count"] == 2
    assert steps["riser_height"] == pytest.approx(0.2)
    assert steps["total_rise"] == pytest.approx(0.4)
    assert steps["start_z"] == pytest.approx(0.0)
    assert steps["end_z"] == pytest.approx(0.4)
    assert platform["connected_opening_id"] == "D1"
    assert steps["connected_opening_id"] == "D1"


def test_level_conflict_fails_closed_after_resolved_host():
    transition = _transition()
    transition["entrance_platform"]["elevation"] = 0.35
    result = ExteriorEntranceGeometryResolverV1().resolve(_geometry(), transition)
    assert result["main_entrance"]["resolution_status"] == "resolved"
    assert result["entrance_threshold"]["resolution_status"] == "pending"
    assert result["exterior_platform_geometry"]["geometry_generation_allowed"] is False
    assert result["entrance_steps_geometry"]["geometry_generation_allowed"] is False


def test_unknown_tread_depth_is_not_defaulted_and_steps_remain_pending():
    result = ExteriorEntranceGeometryResolverV1().resolve(
        _geometry(), _transition(tread_depth=None)
    )
    steps = result["entrance_steps_geometry"]
    assert steps["tread_depth"] is None
    assert steps["geometry_status"] == "pending"
    assert steps["geometry_generation_allowed"] is False


def test_protected_zone_conflict_rejects_platform():
    conflict = {"footprint": {"points": [[4.0, -1.3], [6.0, -1.3], [6.0, -0.1], [4.0, -0.1]]}}
    result = ExteriorEntranceGeometryResolverV1().resolve(
        _geometry(conflicts=[conflict]), _transition()
    )
    assert result["conflict_validation"]["status"] == "conflict"
    assert result["exterior_platform_geometry"]["geometry_status"] == "pending"


def test_design_bim_bridge_preserves_resolved_exterior_entrance_unchanged():
    geometry = _geometry()
    resolved = ExteriorEntranceGeometryResolverV1().resolve(geometry, _transition())
    geometry["site_geometry"]["exterior_entrance"] = resolved
    geometry["architectural_authority"] = True
    project = DesignBIMBridge().prepare_bim_project({
        "architecture_first": True,
        "architectural_geometry": geometry,
        "vertical_section": {"levels": [{"name": "F1", "bottom": 0.4, "top": 3.6}]},
    })
    assert project["geometry"]["site_geometry"]["exterior_entrance"] == resolved


def test_dxf_draws_resolved_transition_and_omits_unresolved_geometry(tmp_path):
    geometry = _geometry()
    resolved = ExteriorEntranceGeometryResolverV1().resolve(geometry, _transition())
    geometry["site_geometry"]["exterior_entrance"] = resolved
    resolved_path = tmp_path / "resolved.dxf"
    DWGWriter().export(geometry, {}, str(resolved_path))
    modelspace = ezdxf.readfile(resolved_path).modelspace()
    assert sum(1 for entity in modelspace if entity.dxf.layer == "EXTERIOR_PLATFORM") == 1
    assert sum(1 for entity in modelspace if entity.dxf.layer == "ENTRANCE_STEPS") == 3
    assert len(modelspace.query("DIMENSION")) == 0

    unresolved_geometry = _geometry(host=None)
    unresolved_geometry["site_geometry"]["exterior_entrance"] = (
        ExteriorEntranceGeometryResolverV1().resolve(unresolved_geometry, _transition())
    )
    unresolved_path = tmp_path / "unresolved.dxf"
    DWGWriter().export(unresolved_geometry, {}, str(unresolved_path))
    unresolved_modelspace = ezdxf.readfile(unresolved_path).modelspace()
    assert sum(1 for entity in unresolved_modelspace if entity.dxf.layer == "EXTERIOR_PLATFORM") == 0
    assert sum(1 for entity in unresolved_modelspace if entity.dxf.layer == "ENTRANCE_STEPS") == 0
