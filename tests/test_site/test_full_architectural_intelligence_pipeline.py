"""
ArchitectOS Full Architectural Intelligence Pipeline Test v1.0
"""


from core.intelligence.architectural_intelligence_orchestrator import (
    ArchitecturalIntelligenceOrchestrator
)

from core.intelligence.architectural_program_integration import (
    ArchitecturalProgramIntegration
)


from core.building.floor_program_engine import (
    FloorProgramEngine
)

from core.spatial.spatial_floor_layout_engine import (
    SpatialFloorLayoutEngine
)

from core.spatial.spatial_unit_placement_engine import (
    SpatialUnitPlacementEngine
)

from core.space.room_program_engine import (
    RoomProgramEngine
)

from core.space.room_layout_engine import (
    RoomLayoutEngine
)

from core.geometry.spatial_geometry_generator import (
    SpatialGeometryGenerator
)

from core.geometry.wall_generator import (
    WallGenerator
)

from core.geometry.opening_placement_engine import (
    OpeningPlacementEngine
)

from core.bim.semantic_bim_mapping_engine import (
    SemanticBIMMappingEngine
)



def test_full_architectural_intelligence_pipeline():


    print(
        "🧠 FULL ARCHITECTURAL INTELLIGENCE PIPELINE v1.0 ACTIVE"
    )


    intelligence_engine = ArchitecturalIntelligenceOrchestrator()

    program_integrator = ArchitecturalProgramIntegration()

    floor_engine = FloorProgramEngine()

    layout_engine = SpatialFloorLayoutEngine()

    unit_engine = SpatialUnitPlacementEngine()

    room_program_engine = RoomProgramEngine()

    room_layout_engine = RoomLayoutEngine()

    geometry_engine = SpatialGeometryGenerator()

    wall_engine = WallGenerator()

    opening_engine = OpeningPlacementEngine()

    bim_engine = SemanticBIMMappingEngine()



    # ============================================
    # BUILDING INTENT
    # ============================================

    intent = {


        "function":
            "commercial",


        "floors":

        [

            {
                "level":"G",
                "type":"commercial"
            },

            {
                "level":"L1",
                "type":"commercial"
            }

        ],


        "public_flow":
            True

    }



    intelligence = intelligence_engine.analyze(

        intent

    )


    print(
        "\n===== INTELLIGENCE PACKAGE ====="
    )

    print(
        intelligence
    )



    # ============================================
    # FLOOR PROGRAM
    # ============================================

    floor_program = floor_engine.generate(

        {

            "level":
                "G",

            "type":
                "commercial"

        }

    )



    floor_program = program_integrator.integrate(

        floor_program,

        intelligence

    )


    print(
        "\n===== PROGRAM ====="
    )

    print(
        floor_program
    )



    # ============================================
    # SPATIAL PIPELINE
    # ============================================

    floor_layout = layout_engine.generate(

        floor_program

    )


    units = unit_engine.generate(

        {
            "level":
                "G"
        },

        1

    )


    room_program = room_program_engine.generate(

        {
            "type":
                "commercial"
        }

    )


    room_layout = room_layout_engine.generate(

        room_program,

        units["units"][0]

    )


    geometry = geometry_engine.generate(

        room_layout,

        units["units"][0]

    )


    walls = wall_engine.generate(

        geometry

    )


    openings = opening_engine.generate(

        {

            "rooms":
                room_layout["rooms"],

            "walls":
                walls["walls"]

        }

    )



    semantic_bim = bim_engine.generate(

        geometry.get(
            "rooms",
            []
        ),

        walls["walls"],

        openings["openings"]

    )



    print(
        "\n========== FINAL RESULT =========="
    )


    print(

        {

            "program_spaces":
                len(
                    floor_program["spaces"]
                ),

            "walls":
                len(
                    walls["walls"]
                ),

            "openings":
                len(
                    openings["openings"]
                ),

            "bim_elements":
                len(
                    semantic_bim["elements"]
                )

        }

    )


    assert len(
        floor_program["spaces"]
    ) > 0


    assert len(
        walls["walls"]
    ) > 0


    assert len(
        semantic_bim["elements"]
    ) > 0



    print(
        "\n✅ FULL ARCHITECTURAL INTELLIGENCE PIPELINE TEST PASSED"
    )



if __name__ == "__main__":

    test_full_architectural_intelligence_pipeline()