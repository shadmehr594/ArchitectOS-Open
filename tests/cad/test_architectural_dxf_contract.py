import ezdxf

from core.export.dwg.dwg_writer import DWGWriter


def test_architectural_dxf_contains_double_walls_openings_and_space_labels(tmp_path):
    output = tmp_path / "architectural_plan.dxf"
    geometry = {
        "physical_walls": [
            {
                "wall_id": "F1-W001",
                "floor": "F1",
                "start": [0.0, 0.0],
                "end": [6.0, 0.0],
                "thickness": 0.30,
            },
        ],
        "spaces": [
            {
                "name": "kitchen",
                "floor": "F1",
                "requirements": {"role": "kitchen"},
                "footprint": {
                    "points": [[0.0, 0.0], [6.0, 0.0], [6.0, 4.0], [0.0, 4.0]],
                },
            },
        ],
        "openings": [
                {
                    "type": "door", "floor": "F1", "width": 1000, "height": 2100,
                    "host_wall_id": "F1-W001", "opening_start": [1.0, 0.0],
                    "opening_end": [2.0, 0.0], "geometry_status": "resolved",
                },
                {
                    "type": "window", "floor": "F1", "width": 1800, "height": 1200,
                    "host_wall_id": "F1-W001", "opening_start": [3.0, 0.0],
                    "opening_end": [4.8, 0.0], "geometry_status": "resolved",
            },
        ],
        "external_spaces": [
            {
                "name": "yard",
                "type": "yard",
                "footprint": {
                    "points": [[-2.0, -2.0], [8.0, -2.0], [8.0, 6.0], [-2.0, 6.0]],
                },
            },
        ],
    }

    result = DWGWriter().export(geometry, {}, output=str(output))

    assert result["status"] == "exported"
    modelspace = ezdxf.readfile(output).modelspace()

    wall_lines = [
        entity for entity in modelspace
        if entity.dxftype() == "LINE" and entity.dxf.layer == "F1_WALLS"
    ]
    assert len(wall_lines) == 2
    assert {round(float(line.dxf.start.y), 3) for line in wall_lines} == {-0.15, 0.15}

    door_entities = [entity for entity in modelspace if entity.dxf.layer == "F1_DOORS"]
    assert {entity.dxftype() for entity in door_entities} == {"LINE", "ARC"}

    window_lines = [
        entity for entity in modelspace
        if entity.dxftype() == "LINE" and entity.dxf.layer == "F1_WINDOWS"
    ]
    assert len(window_lines) == 3

    labels = [
        entity.text for entity in modelspace
        if entity.dxftype() == "MTEXT"
    ]
    assert any("KITCHEN" in label and "آشپزخانه" in label for label in labels)
    assert any("YARD" in label and "حیاط" in label for label in labels)
    assert any(
        entity.dxftype() == "LWPOLYLINE" and entity.dxf.layer == "F1_ROOMS"
        for entity in modelspace
    )
    assert any(
        entity.dxftype() == "LWPOLYLINE" and entity.dxf.layer == "EXTERNAL_SPACE"
        for entity in modelspace
    )


def test_dxf_draws_stairs_furniture_circulation_columns_and_beams(tmp_path):
    output = tmp_path / "coordinated_plan.dxf"
    spaces = [
        {"id": "hall", "name": "corridor", "floor": "F1", "footprint": {"points": [[0, 0], [3, 0], [3, 2], [0, 2]]}},
        {"id": "living", "name": "living", "floor": "F1", "footprint": {"points": [[3, 0], [7, 0], [7, 4], [3, 4]]}},
    ]
    geometry = {
        "spaces": spaces,
        "circulation": [["hall", "living"]],
        "stairs": [{"footprint": {"points": [[0, 2], [2, 2], [2, 6], [0, 6]]}, "riser_count": 10}],
        "furniture": [{"type": "sofa", "footprint": {"points": [[4, 1], [6, 1], [6, 2], [4, 2]]}}],
    }
    structure = {
        "columns": [{"x": 1, "y": 1, "width": 0.4, "depth": 0.4}],
        "beams": [{"start": [1, 1], "end": [6, 1]}],
    }

    DWGWriter().export(geometry, structure, output=str(output))
    modelspace = ezdxf.readfile(output).modelspace()
    layers = {entity.dxf.layer for entity in modelspace}
    assert {"ARCH_STAIRS", "ARCH_FURNITURE", "ARCH_CIRCULATION", "STRUCT_COLUMNS", "STRUCT_BEAMS"} <= layers
    stair_text = [entity.dxf.text for entity in modelspace if entity.dxftype() == "TEXT" and entity.dxf.layer == "ARCH_STAIRS"]
    assert "UP / START" in stair_text
    assert "END" in stair_text


def test_canonical_openings_override_incomplete_legacy_first_floor_doors(tmp_path):
    output = tmp_path / "all_storey_doors.dxf"
    geometry = {
        "physical_walls": [
            {"wall_id": "F1-W", "floor": "F1", "start": [0, 0], "end": [4, 0], "thickness": 0.2},
            {"wall_id": "F2-W", "floor": "F2", "start": [0, 0], "end": [4, 0], "thickness": 0.2},
        ],
            "doors": [{"type": "door", "floor": "F1", "host_wall_id": "F1-W",
                       "opening_start": [1, 0], "opening_end": [1.9, 0],
                       "width": 900, "height": 2100, "geometry_status": "resolved"}],
            "openings": [
                {"type": "door", "floor": "F1", "host_wall_id": "F1-W",
                 "opening_start": [1, 0], "opening_end": [1.9, 0],
                 "width": 900, "height": 2100, "geometry_status": "resolved"},
                {"type": "door", "floor": "F2", "host_wall_id": "F2-W",
                 "opening_start": [1, 0], "opening_end": [1.9, 0],
                 "width": 900, "height": 2100, "geometry_status": "resolved"},
            ],
    }
    DWGWriter().export(geometry, {}, output=str(output))
    msp = ezdxf.readfile(output).modelspace()
    assert sum(1 for e in msp if e.dxf.layer == "F1_DOORS") == 2
    assert sum(1 for e in msp if e.dxf.layer == "F2_DOORS") == 2
