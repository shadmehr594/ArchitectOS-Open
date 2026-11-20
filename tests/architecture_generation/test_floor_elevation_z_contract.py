from core.architecture.geometry.architectural_geometry_engine_v2 import (
    ArchitecturalGeometryEngineV2,
)
from core.architecture.geometry.architectural_geometry_intent_generator_v1 import (
    ArchitecturalGeometryIntentGeneratorV1,
)


def test_vertical_section_level_bounds_flow_to_architectural_slabs_unchanged():
    placement = {
        "floors": {
            "lower": {
                "height": 99.0,
                "spaces": [
                    {
                        "name": "living",
                        "x": 0.0,
                        "y": 0.0,
                        "width": 4.0,
                        "depth": 3.0,
                    }
                ],
            },
            "upper": {
                "height": 88.0,
                "spaces": [
                    {
                        "name": "bedroom",
                        "x": 0.0,
                        "y": 0.0,
                        "width": 4.0,
                        "depth": 3.0,
                    }
                ],
            },
        },
        "vertical_core": [
            {
                "name": "stairs",
                "connects": ["lower", "upper"],
                "continuous": True,
            },
            {
                "name": "elevator",
                "connects": ["upper"],
                "continuous": True,
            },
            {
                "name": "ramp",
                "connects": ["SITE", "lower"],
                "continuous": False,
            },
            {
                "name": "service_core",
                "continuous": True,
            },
            {
                "name": "unresolved_core",
                "connects": ["missing_level"],
                "continuous": True,
            },
        ],
    }
    vertical_section = {
        "levels": [
            {"name": "lower", "bottom": -2.75, "top": 1.125, "height": 3.875},
            {"name": "upper", "bottom": 7.625, "top": 12.875, "height": 5.25},
        ],
        "roof_level": 12.875,
        # Deliberately contradictory legacy data: levels must win.
        "floor_elevations": {"lower": 1000.0, "upper": 2000.0},
    }

    geometry_intent = ArchitecturalGeometryIntentGeneratorV1().generate(
        placement,
        vertical_section=vertical_section,
    )
    architectural_geometry = ArchitecturalGeometryEngineV2().generate(
        geometry_intent
    )

    intent_by_floor = {
        item["floor"]: item
        for item in geometry_intent["floor_geometry_intent"]
    }
    floor_geometry_by_floor = {
        item["floor"]: item
        for item in architectural_geometry["floor_geometry"]
    }
    slabs_by_floor = {
        item["floor"]: item
        for item in architectural_geometry["slabs"]
    }
    boundaries_by_floor = {
        item["floor"]: item
        for item in architectural_geometry["boundaries"]
    }

    intent_spaces_by_floor = {
        item["floor"]: item
        for item in geometry_intent["spaces"]
    }
    geometry_spaces_by_floor = {
        item["floor"]: item
        for item in architectural_geometry["spaces"]
    }

    expected = {
        "lower": (-2.75, 1.125, 3.875),
        "upper": (7.625, 12.875, 5.25),
    }

    for floor, (bottom, top, height) in expected.items():
        assert intent_by_floor[floor]["bottom"] == bottom
        assert intent_by_floor[floor]["top"] == top
        assert intent_by_floor[floor]["elevation"] == bottom
        assert intent_by_floor[floor]["height"] == height
        assert intent_by_floor[floor]["height_status"] == (
            "resolved_from_vertical_section_level"
        )

        assert floor_geometry_by_floor[floor]["bottom"] == bottom
        assert floor_geometry_by_floor[floor]["top"] == top
        assert floor_geometry_by_floor[floor]["elevation"] == bottom

        assert slabs_by_floor[floor]["bottom"] == bottom
        assert slabs_by_floor[floor]["top"] == top
        assert slabs_by_floor[floor]["elevation"] == bottom

        assert intent_spaces_by_floor[floor]["bottom"] == bottom
        assert intent_spaces_by_floor[floor]["top"] == top
        assert intent_spaces_by_floor[floor]["elevation"] == bottom
        assert intent_spaces_by_floor[floor]["height"] == height

        assert geometry_spaces_by_floor[floor]["bottom"] == bottom
        assert geometry_spaces_by_floor[floor]["top"] == top
        assert geometry_spaces_by_floor[floor]["elevation"] == bottom
        assert geometry_spaces_by_floor[floor]["height"] == height

        assert boundaries_by_floor[floor]["bottom"] == bottom
        assert boundaries_by_floor[floor]["top"] == top
        assert boundaries_by_floor[floor]["height"] == height

        floor_segments = [
            item
            for item in architectural_geometry["boundary_segments"]
            if item["floor"] == floor
        ]
        assert floor_segments
        assert all(item["bottom"] == bottom for item in floor_segments)
        assert all(item["top"] == top for item in floor_segments)
        assert all(item["height"] == height for item in floor_segments)

        floor_walls = [
            item
            for item in architectural_geometry["physical_walls"]
            if item["floor"] == floor
        ]
        assert floor_walls
        assert all(item["bottom"] == bottom for item in floor_walls)
        assert all(item["top"] == top for item in floor_walls)
        assert all(item["height"] == height for item in floor_walls)

        floor_openings = [
            item
            for item in architectural_geometry["openings"]
            if item["floor"] == floor
        ]
        assert floor_openings
        assert all(item["level_bottom"] == bottom for item in floor_openings)
        assert all(item["level_top"] == top for item in floor_openings)
        assert all(item["level_height"] == height for item in floor_openings)

    intent_cores = {
        item["name"]: item
        for item in geometry_intent["vertical_elements"]
    }
    geometry_cores = {
        item["name"]: item
        for item in architectural_geometry["vertical_geometry"]
    }

    expected_core_spans = {
        "stairs": (-2.75, 12.875, ["lower", "upper"]),
        "elevator": (7.625, 12.875, ["upper"]),
        "ramp": (-2.75, 1.125, ["lower"]),
        "service_core": (-2.75, 12.875, ["lower", "upper"]),
    }

    for name, (bottom, top, served_levels) in expected_core_spans.items():
        assert intent_cores[name]["bottom"] == bottom
        assert intent_cores[name]["top"] == top
        assert intent_cores[name]["served_levels"] == served_levels
        assert intent_cores[name]["span_status"] == (
            "resolved_from_vertical_section_levels"
        )

        assert geometry_cores[name]["bottom"] == bottom
        assert geometry_cores[name]["top"] == top
        assert geometry_cores[name]["served_levels"] == served_levels
        assert geometry_cores[name]["span_status"] == (
            "resolved_from_vertical_section_levels"
        )

    assert intent_cores["service_core"]["span_source"] == (
        "continuous_all_levels"
    )
    assert geometry_cores["service_core"]["span_source"] == (
        "continuous_all_levels"
    )

    assert intent_cores["unresolved_core"]["bottom"] is None
    assert intent_cores["unresolved_core"]["top"] is None
    assert intent_cores["unresolved_core"]["served_levels"] == []
    assert intent_cores["unresolved_core"]["span_status"] == (
        "vertical_core_span_unresolved"
    )
    assert geometry_cores["unresolved_core"]["bottom"] is None
    assert geometry_cores["unresolved_core"]["top"] is None
    assert geometry_cores["unresolved_core"]["span_status"] == (
        "vertical_core_span_unresolved"
    )

    roof_intent = geometry_intent["roof_geometry_intent"]
    roof_geometry = architectural_geometry["roof_geometry"]

    assert roof_intent["roof_level"] == 12.875
    assert roof_intent["source_level"] == "upper"
    assert roof_intent["source_level_top"] == 12.875
    assert roof_intent["z_contract_status"] == (
        "consistent_with_last_level_top"
    )

    assert roof_geometry["roof_level"] == 12.875
    assert roof_geometry["source_level"] == "upper"
    assert roof_geometry["source_level_top"] == 12.875
    assert roof_geometry["z_contract_status"] == (
        "consistent_with_last_level_top"
    )


def test_conflicting_roof_z_evidence_is_preserved_without_recalculation():
    placement = {
        "floors": {
            "roof_source": {
                "spaces": [
                    {
                        "name": "living",
                        "x": 0.0,
                        "y": 0.0,
                        "width": 2.0,
                        "depth": 2.0,
                    }
                ]
            }
        }
    }
    vertical_section = {
        "levels": [
            {
                "name": "roof_source",
                "bottom": 3.0,
                "top": 8.25,
                "height": 5.25,
            }
        ],
        "roof_level": 99.5,
    }

    geometry_intent = ArchitecturalGeometryIntentGeneratorV1().generate(
        placement,
        vertical_section=vertical_section,
    )
    architectural_geometry = ArchitecturalGeometryEngineV2().generate(
        geometry_intent
    )

    roof_intent = geometry_intent["roof_geometry_intent"]
    roof_geometry = architectural_geometry["roof_geometry"]

    assert roof_intent["roof_level"] == 99.5
    assert roof_intent["source_level_top"] == 8.25
    assert roof_intent["z_contract_status"] == (
        "conflicting_roof_level_and_last_level_top"
    )

    assert roof_geometry["roof_level"] == 99.5
    assert roof_geometry["source_level_top"] == 8.25
    assert roof_geometry["z_contract_status"] == (
        "conflicting_roof_level_and_last_level_top"
    )
