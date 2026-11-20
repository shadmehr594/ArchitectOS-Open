from core.architecture.geometry.architectural_geometry_engine_v2 import (
    ArchitecturalGeometryEngineV2,
)
from core.architecture.geometry.architectural_geometry_intent_generator_v1 import (
    ArchitecturalGeometryIntentGeneratorV1,
)
from core.architecture.geometry.architectural_geometry_pipeline_v1 import (
    ArchitecturalGeometryPipelineV1,
)
from core.architecture.reasoning.architectural_element_placement_reasoner_v3 import (
    ArchitecturalElementPlacementReasonerV3,
)
from core.architecture.reasoning.architectural_layout_intent_resolver_v1 import (
    ArchitecturalLayoutIntentResolverV1,
)
from core.architecture.vertical_building_section_engine import (
    VerticalBuildingSectionEngine,
)


def _spatial_contract():
    return {
        "spaces": [
            {
                "name": "living",
                "floor": "F1",
                "zone": "public",
                "role": "living",
                "x": 0.0,
                "y": 0.0,
                "width": 4.0,
                "depth": 3.0,
                "resolved_dimensions": {
                    "width": 4.0,
                    "depth": 3.0,
                    "area": 12.0,
                },
                "coordinate_mode": "architectural_metric",
            },
            {
                "name": "bedroom",
                "floor": "F2",
                "zone": "private",
                "role": "bedroom",
                "x": 0.0,
                "y": 0.0,
                "width": 3.0,
                "depth": 3.0,
                "resolved_dimensions": {
                    "width": 3.0,
                    "depth": 3.0,
                    "area": 9.0,
                },
                "coordinate_mode": "architectural_metric",
            },
        ],
        "adjacency": [],
        "vertical_organization": {
            "F1": ["living"],
            "F2": ["bedroom"],
        },
        "floor_heights": {
            "F1": 3.15,
            "F2": 4.35,
        },
        "floor_configuration": {
            "source": "architecture_completion_gate",
        },
    }


def test_architecture_completion_gate_from_contract_to_geometry():
    spatial_contract = _spatial_contract()
    vertical_section = VerticalBuildingSectionEngine().generate(
        spatial_contract
    )
    layout_intent = ArchitecturalLayoutIntentResolverV1().resolve(
        spatial_contract
    )
    placement = ArchitecturalElementPlacementReasonerV3().generate(
        layout_intent,
        spatial_contract,
        {
            "vertical_systems": [
                {
                    "type": "stairs",
                    "connects": ["F1", "F2"],
                    "continuous": True,
                }
            ]
        },
    )
    geometry_intent = ArchitecturalGeometryIntentGeneratorV1().generate(
        placement,
        vertical_section=vertical_section,
    )
    architectural_geometry = ArchitecturalGeometryEngineV2().generate(
        geometry_intent
    )

    levels = {
        level["name"]: level
        for level in vertical_section["levels"]
    }
    assert levels == {
        "F1": {
            "name": "F1",
            "type": "residential",
            "type_status": "resolved",
            "type_source": "floor_program_space_roles",
            "type_evidence": [{"kind": "program_space_roles", "level": "F1", "roles": ["living"]}],
            "bottom": 0.0,
            "top": 3.15,
            "height": 3.15,
            "height_source": "architecture_completion_gate",
            "height_status": "resolved",
        },
        "F2": {
            "name": "F2",
            "type": "residential",
            "type_status": "resolved",
            "type_source": "floor_program_space_roles",
            "type_evidence": [{"kind": "program_space_roles", "level": "F2", "roles": ["bedroom"]}],
            "bottom": 3.15,
            "top": 7.5,
            "height": 4.35,
            "height_source": "architecture_completion_gate",
            "height_status": "resolved",
        },
    }

    floor_scoped_collections = (
        geometry_intent["floor_geometry_intent"],
        geometry_intent["spaces"],
        architectural_geometry["spaces"],
        architectural_geometry["boundaries"],
        architectural_geometry["boundary_segments"],
        architectural_geometry["physical_walls"],
        architectural_geometry["floor_geometry"],
    )

    for collection in floor_scoped_collections:
        assert collection
        for item in collection:
            level = levels[item["floor"]]
            assert item["bottom"] == level["bottom"]
            assert item["top"] == level["top"]
            assert item["height"] == level["height"]

    assert architectural_geometry["slabs"]
    for slab in architectural_geometry["slabs"]:
        level = levels[slab["floor"]]
        assert slab["bottom"] == level["bottom"]
        assert slab["top"] == level["top"]

    assert architectural_geometry["openings"]
    for opening in architectural_geometry["openings"]:
        level = levels[opening["floor"]]
        assert opening["level_bottom"] == level["bottom"]
        assert opening["level_top"] == level["top"]
        assert opening["level_height"] == level["height"]

    stairs_intent = geometry_intent["vertical_elements"][0]
    stairs_geometry = architectural_geometry["vertical_geometry"][0]
    assert stairs_intent["bottom"] == levels["F1"]["bottom"]
    assert stairs_intent["top"] == levels["F2"]["top"]
    assert stairs_geometry["bottom"] == levels["F1"]["bottom"]
    assert stairs_geometry["top"] == levels["F2"]["top"]

    roof_intent = geometry_intent["roof_geometry_intent"]
    roof_geometry = architectural_geometry["roof_geometry"]
    assert roof_intent["roof_level"] == levels["F2"]["top"]
    assert roof_intent["z_contract_status"] == (
        "consistent_with_last_level_top"
    )
    assert roof_geometry["roof_level"] == levels["F2"]["top"]
    assert roof_geometry["z_contract_status"] == (
        "consistent_with_last_level_top"
    )


def test_geometry_pipeline_forwards_vertical_section_unchanged():
    vertical_section = {
        "levels": [
            {"name": "F1", "bottom": -1.25, "top": 2.75, "height": 4.0}
        ],
        "roof_level": 2.75,
    }
    captured = {}

    class IntentGenerator:
        def generate(self, placement_output, **kwargs):
            captured.update(kwargs)
            return {"floor_geometry_intent": []}

    class GeometryEngine:
        def generate(self, geometry_intent):
            return {"geometry_intent_seen": geometry_intent}

    class Converter:
        def convert(self, geometry):
            return {}

    class Enricher:
        def enrich(self, architectural_bim):
            return {}

    class FacadeBridge:
        def resolve(self, facade_context):
            return {}

    pipeline = ArchitecturalGeometryPipelineV1.__new__(
        ArchitecturalGeometryPipelineV1
    )
    pipeline.intent_generator = IntentGenerator()
    pipeline.geometry_engine = GeometryEngine()
    pipeline.geometry_to_bim = Converter()
    pipeline.bim_enrichment = Enricher()
    pipeline.facade_bridge = FacadeBridge()

    pipeline.generate({}, vertical_section=vertical_section)

    assert captured["vertical_section"] is vertical_section
