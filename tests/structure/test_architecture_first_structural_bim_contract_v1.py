from core.cad.cad_import_engine import CADImportEngine
from core.architecture.reasoning.site_reasoner import SiteReasoner
from core.architecture.reasoning.knowledge_space_generator import (
    KnowledgeSpaceGenerator
)
from core.architecture.reasoning.layout_reasoner import LayoutReasoner
from core.architecture.geometry.architectural_geometry_intent_generator_v1 import (
    ArchitecturalGeometryIntentGeneratorV1
)
from core.architecture.geometry.architectural_geometry_engine_v2 import (
    ArchitecturalGeometryEngineV2
)
from core.structure.structural_grid_engine import StructuralGridEngine
from core.integration.design_bim_bridge import DesignBIMBridge
from core.bim.full_bim_pipeline import FullBIMPipeline


def test_architecture_first_structural_bim_contract_v1():

    print(
        "\n"
        "============================================================"
    )

    print(
        "ARCHITECTURE-FIRST STRUCTURAL BIM CONTRACT V1"
    )

    print(
        "============================================================"
    )


    # ==================================================
    # STEP 1
    # REAL SITE
    # ==================================================

    cad = CADImportEngine().load(
        {
            "file_object":
                r"tests\data\real_site\parcel_2_source.dxf"
        },
        target_parcel=2
    )


    site_analysis = SiteReasoner().analyze(
        cad["site"]
    )


    # ==================================================
    # STEP 2
    # ARCHITECTURAL PROGRAM
    # ==================================================

    space_result = KnowledgeSpaceGenerator().generate(
        {
            "building_type":
                "villa"
        }
    )


    layout = LayoutReasoner().generate(
        space_result[
            "generated_spaces"
        ],
        space_result[
            "relationships"
        ],
        {
            "building_type":
                "villa"
        },
        space_result[
            "generated_spaces"
        ],
        site_analysis
    )


    # ==================================================
    # STEP 3
    # ARCHITECTURAL GEOMETRY
    # ==================================================

    vertical_section = {
        "levels": [
            {
                "name": "ground_floor",
                "bottom": -0.35,
                "top": 3.2,
                "height": 3.55,
            },
            {
                "name": "upper_floor",
                "bottom": 3.2,
                "top": 6.85,
                "height": 3.65,
            },
        ],
        "roof_level": 6.85,
    }

    geometry_intent = (
        ArchitecturalGeometryIntentGeneratorV1().generate(
            layout,
            site_analysis=site_analysis,
            vertical_section=vertical_section,
        )
    )


    architectural_geometry = (
        ArchitecturalGeometryEngineV2().generate(
            geometry_intent
        )
    )


    architectural_spaces = [

        {
            "name":
                space.get(
                    "name"
                ),

            "floor":
                space.get(
                    "floor"
                ),

            "type":
                space.get(
                    "type"
                ),

            "protected_zone":
                space.get(
                    "protected_zone"
                ),

            "coordinate_mode":
                space.get(
                    "resolved_coordinate_mode",
                    space.get(
                        "coordinate_mode"
                    )
                ),

            "geometry_status":
                space.get(
                    "geometry_status"
                ),

            "footprint":
                space.get(
                    "footprint"
                )
        }

        for space in architectural_geometry.get(
            "spaces",
            []
        )

    ]


    # ==================================================
    # STEP 4
    # ARCHITECTURE-FIRST STRUCTURAL MODEL
    # ==================================================

    structural_model = {

        "building":
            {
                "width":
                    16,

                "depth":
                    16
            },

        "spaces":
            [],

        "architectural_spaces":
            architectural_spaces,

        "architectural_geometry":
            architectural_geometry,

        "coordinate_frame":
            architectural_geometry.get(
                "coordinate_frame",
                {}
            ),

        "parcel_placement":
            architectural_geometry.get(
                "parcel_placement",
                {}
            ),

        "architecture_first":
            True
    }


    structural_grid = StructuralGridEngine().build(
        structural_model,
        vertical_section
    )


    # ==================================================
    # STEP 5
    # STRUCTURAL CONTRACT VALIDATION
    # ==================================================

    print(
        "\n====== STRUCTURAL GRID CONTRACT ======"
    )

    print(
        "GRID TYPE:",
        structural_grid.get(
            "grid_type"
        )
    )

    print(
        "ANCHOR OWNERSHIP:",
        structural_grid.get(
            "anchor_ownership"
        )
    )

    print(
        "MASTER X:",
        structural_grid.get(
            "master_x_anchors"
        )
    )

    print(
        "MASTER Y:",
        structural_grid.get(
            "master_y_anchors"
        )
    )

    print(
        "FLOOR SYSTEMS:",
        {
            floor:
                {
                    "topology_mode":
                        data.get(
                            "topology_mode"
                        ),

                    "columns":
                        len(
                            data.get(
                                "columns",
                                []
                            )
                        ),

                    "beams":
                        len(
                            data.get(
                                "beams",
                                []
                            )
                        )
                }

            for floor, data
            in structural_grid.get(
                "floor_structural_systems",
                {}
            ).items()
        }
    )

    print(
        "======================================"
    )


    assert (
        structural_grid.get(
            "grid_type"
        )
        ==
        "adaptive"
    )


    assert (
        structural_grid.get(
            "anchor_ownership"
        )
        ==
        "architectural_support_domains"
    )


    assert structural_grid.get(
        "master_x_anchors"
    )


    assert structural_grid.get(
        "master_y_anchors"
    )


    floor_systems = structural_grid.get(
        "floor_structural_systems",
        {}
    )


    assert (
        "ground_floor"
        in floor_systems
    )


    assert (
        "upper_floor"
        in floor_systems
    )


    assert (
        floor_systems[
            "ground_floor"
        ].get(
            "topology_mode"
        )
        ==
        "base_structural_grid"
    )


    assert (
        floor_systems[
            "upper_floor"
        ].get(
            "topology_mode"
        )
        ==
        "vertical_grid_inheritance"
    )


    # ==================================================
    # STEP 6
    # PREPARE BIM INPUT
    #
    # IMPORTANT:
    # StructuralGridEngine output is authoritative.
    # BIM must preserve this exact contract.
    # ==================================================

    design_result = {

        "type":
            "design",

        "site":
            site_analysis,

        "spatial":
            {
                "ground_floor": {
                    "nodes": {}
                },

                "upper_floor": {
                    "nodes": {}
                }
            },

        "structural_grid":
            structural_grid,

        "geometry":
            architectural_geometry,

        "generate_structure":
            True
    }


    bridge = DesignBIMBridge()


    bim_project = bridge.prepare_bim_project(
        design_result
    )

    print(
        "\n====== BIM PROJECT INPUT CONTRACT ======"
    )

    print(
        "PROJECT KEYS:",
        bim_project.keys()
    )

    print(
        "SPATIAL TYPE:",
        type(
            bim_project.get(
                "spatial"
            )
        ).__name__
    )

    print(
        "SPATIAL VALUE:",
        bim_project.get(
            "spatial"
        )
    )

    print(
        "SPATIAL BOOL:",
        bool(
            bim_project.get(
                "spatial"
            )
        )
    )

    print(
        "GEOMETRY TYPE:",
        type(
            bim_project.get(
                "geometry"
            )
        ).__name__
    )

    print(
        "GEOMETRY KEYS:",
        list(
            bim_project.get(
                "geometry",
                {}
            ).keys()
        )
    )

    print(
        "STRUCTURAL GRID:",
        bool(
            bim_project.get(
                "structural_grid"
            )
        )
    )

    print(
        "========================================"
    )


    bridged_grid = bim_project.get(
        "structural_grid",
        {}
    )


    print(
        "\n====== BRIDGE STRUCTURAL CONTRACT ======"
    )

    print(
        "SAME GRID CONTRACT:",
        bridged_grid
        ==
        structural_grid
    )

    print(
        "GRID TYPE:",
        bridged_grid.get(
            "grid_type"
        )
    )

    print(
        "ANCHOR OWNERSHIP:",
        bridged_grid.get(
            "anchor_ownership"
        )
    )

    print(
        "MASTER X:",
        bridged_grid.get(
            "master_x_anchors"
        )
    )

    print(
        "MASTER Y:",
        bridged_grid.get(
            "master_y_anchors"
        )
    )

    print(
        "========================================"
    )


    assert (
        bridged_grid
        ==
        structural_grid
    )


    assert (
        bridged_grid.get(
            "anchor_ownership"
        )
        ==
        "architectural_support_domains"
    )


    # ==================================================
    # STEP 7
    # FULL BIM
    # ==================================================

    result = FullBIMPipeline().generate(
        bim_project
    )


    assert result is not None


    assert (
        result.get(
            "status"
        )
        ==
        "completed"
    )


    final_structure = result.get(
        "structure",
        {}
    )


    # ==================================================
    # STEP 8
    # FINAL STRUCTURAL BIM VALIDATION
    # ==================================================

    print(
        "\n====== FINAL BIM STRUCTURE ======"
    )

    print(
        "COLUMNS:",
        len(
            final_structure.get(
                "columns",
                []
            )
        )
    )

    print(
        "BEAMS:",
        len(
            final_structure.get(
                "beams",
                []
            )
        )
    )


    for column in final_structure.get(
        "columns",
        []
    )[:20]:

        print(
            "COLUMN:",
            column.get(
                "id"
            ),
            column.get(
                "level"
            ),
            column.get(
                "x"
            ),
            column.get(
                "y"
            ),
            column.get(
                "z"
            )
        )


    for beam in final_structure.get(
        "beams",
        []
    )[:20]:

        print(
            "BEAM:",
            beam.get(
                "id"
            ),
            beam.get(
                "level"
            ),
            beam.get(
                "start"
            ),
            beam.get(
                "end"
            ),
            beam.get(
                "z"
            )
        )


    print(
        "================================="
    )


    assert final_structure.get(
        "columns"
    )


    assert final_structure.get(
        "beams"
    )


    print(
        "\n"
        "ARCHITECTURE-FIRST STRUCTURAL BIM CONTRACT V1 PASSED"
    )
