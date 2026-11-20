"""
ArchitectOS Full Architectural Generation Pipeline Test v1.0
"""


from core.building.building_stack_generator import (
    BuildingStackGenerator
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



def test_full_architectural_generation_pipeline():


    print(
        "🏛️ FULL ARCHITECTURAL GENERATION PIPELINE v1.0 ACTIVE"
    )


    stack_engine = BuildingStackGenerator()

    floor_engine = FloorProgramEngine()

    layout_engine = SpatialFloorLayoutEngine()

    unit_engine = SpatialUnitPlacementEngine()

    room_program_engine = RoomProgramEngine()

    room_layout_engine = RoomLayoutEngine()

    geometry_engine = SpatialGeometryGenerator()

    wall_engine = WallGenerator()

    opening_engine = OpeningPlacementEngine()

    bim_engine = SemanticBIMMappingEngine()



    stack = stack_engine.generate(

        {
            "site":
            {
                "width":20,
                "depth":30
            },

            "floors":[

                {
                    "level":"B1",
                    "type":"parking",
                    "features":[
                        "ramp",
                        "caretaker"
                    ]
                },

                {
                    "level":"G",
                    "type":"commercial",
                    "features":[
                        "mezzanine"
                    ]
                },

                {
                    "level":"F1",
                    "type":"residential",
                    "units":4
                },

                {
                    "level":"F2",
                    "type":"residential",
                    "units":3,
                    "projection":
                    {
                        "side":"south",
                        "width":8,
                        "depth":1.5
                    }
                },

                {
                    "level":"F3",
                    "type":"duplex",
                    "units":2
                },

                {
                    "level":"PH",
                    "type":"penthouse"
                }

            ]

        }

    )


    print(
        "\nSTACK OK:",
        stack["floor_count"]
    )



    floor_program = floor_engine.generate(

        {
            "level":"F1",
            "type":"residential",
            "units":4
        }

    )


    floor_layout = layout_engine.generate(

        floor_program

    )


    units = unit_engine.generate(

        {
            "level":
                "F1"
        },

        4

    )


    unit = units["units"][0]


    room_program = room_program_engine.generate(

        {
            "type":
                "residential"
        }

    )


    room_layout = room_layout_engine.generate(

        room_program,

        unit

    )

    spaces = room_layout["rooms"]


    geometry = geometry_engine.generate(

        room_layout,

        unit

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


    print("\n===== SEMANTIC BIM INPUT DEBUG =====")

    print("SPACES TYPE:", type(spaces))

    if isinstance(spaces, list):
        print("SPACES COUNT:", len(spaces))
        print("SPACE SAMPLE:", spaces[:1])

    print("WALLS TYPE:", type(walls))
    print("OPENINGS TYPE:", type(openings))

    print("====================================\n")


    semantic_bim = bim_engine.generate(

        spaces,

        walls["walls"],

        openings["openings"]

    )



    print(
        "\n========== FINAL RESULT =========="
    )


    print(
        {
            "floors":
                stack["floor_count"],

            "units":
                len(
                    units.get(
                        "units",
                        []
                    )
                ),

            "walls":
                len(
                    walls.get(
                        "walls",
                        []
                    )
                ),

            "openings":
                len(
                    openings.get(
                        "openings",
                        []
                    )
                ),

            "bim_elements":
                len(
                    semantic_bim.get(
                        "elements",
                        []
                    )
                )
        }
    )


    assert stack["floor_count"] == 6

    assert len(
        walls["walls"]
    ) > 0


    assert len(
        openings["openings"]
    ) > 0


    assert len(
        semantic_bim["elements"]
    ) > 0



    print(
        "\n✅ FULL ARCHITECTURAL GENERATION PIPELINE TEST PASSED"
    )



if __name__ == "__main__":

    test_full_architectural_generation_pipeline()