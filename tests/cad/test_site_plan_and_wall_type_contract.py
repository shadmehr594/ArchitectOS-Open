import ezdxf

from core.export.dwg.dwg_writer import DWGWriter
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent
from core.architecture.geometry.architectural_physical_wall_resolver_v1 import ArchitecturalPhysicalWallResolverV1


def test_bot_extracts_wall_types_and_site_access_requirements():
    intent = ArchitecturalIntent().extract(
        "دیوار داخلی 10 سانت، دیوار خارجی 35 سانت و دیوار حیاط 20 سانت؛ "
        "معبر 12 متر با دسترسی خودرو و دسترسی پیاده و فضای سبز"
    )
    assert intent["wall_thicknesses"] == {"interior": 0.10, "exterior": 0.35, "yard": 0.20}
    constraints = intent["site_constraints"]
    assert constraints["road"]["width"] == 12.0
    assert constraints["vehicle_access"]["required"] is True
    assert constraints["pedestrian_access"]["required"] is True
    assert constraints["landscape"]["required"] is True
    assert constraints["boundary_wall"]["thickness"] == 0.20


def test_site_plan_dxf_has_road_access_landscape_wall_and_level_codes(tmp_path):
    output = tmp_path / "site_plan.dxf"
    geometry = {
        "slabs": [{"floor": "F1", "bottom": 0.0, "footprint": {"points": [[2, 2], [8, 2], [8, 7], [2, 7]]}}],
        "site_plan": {
            "road": {"start": [0, 0], "end": [10, 0], "width": 12},
            "vehicle_access": {"points": [[2, 0], [2, 3]]},
            "pedestrian_access": {"points": [[8, 0], [8, 2]]},
            "landscape": [{"footprint": {"points": [[0, 4], [2, 4], [2, 8], [0, 8]]}}],
            "boundary_walls": [{"start": [0, 0], "end": [0, 10], "thickness": 0.20}],
        },
    }
    DWGWriter().export(geometry, {}, output=str(output))
    msp = ezdxf.readfile(output).modelspace()
    layers = {e.dxf.layer for e in msp}
    assert {"SITE_ROAD", "SITE_VEHICLE_ACCESS", "SITE_PEDESTRIAN_ACCESS", "SITE_LANDSCAPE", "SITE_BOUNDARY_WALLS", "SITE_LEVELS"} <= layers
    level_labels = [e.dxf.text for e in msp if e.dxftype() == "TEXT" and e.dxf.layer == "SITE_LEVELS"]
    assert "F1  +0.00" in level_labels


def test_physical_walls_use_requested_interior_and_exterior_types():
    segments = [
        {"floor": "F1", "start": [0, 0], "end": [4, 0], "space": "A", "boundary_id": "a", "boundary_type": "exterior"},
        {"floor": "F1", "start": [0, 2], "end": [4, 2], "space": "A", "boundary_id": "b1", "boundary_type": "shared"},
        {"floor": "F1", "start": [4, 2], "end": [0, 2], "space": "B", "boundary_id": "b2", "boundary_type": "shared"},
    ]
    walls = ArchitecturalPhysicalWallResolverV1().resolve(
        segments, {"interior": 0.15, "exterior": 0.35}
    )
    by_type = {wall["wall_type"]: wall for wall in walls}
    assert by_type["exterior_wall"]["thickness"] == 0.35
    assert by_type["interior_shared_wall"]["thickness"] == 0.15
