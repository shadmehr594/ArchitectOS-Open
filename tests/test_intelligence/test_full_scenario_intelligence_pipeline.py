"""
ArchitectOS Full Scenario Intelligence Pipeline v1.0
"""


from core.intelligence.scenario_program_adapter import (
    ScenarioProgramAdapter
)

from core.building.floor_program_engine import (
    FloorProgramEngine
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



def test_full_scenario_intelligence_pipeline():


    print(
        "🧠 FULL SCENARIO INTELLIGENCE PIPELINE v1.0 ACTIVE"
    )



    scenario_adapter = ScenarioProgramAdapter()

    floor_engine = FloorProgramEngine()

    room_program_engine = RoomProgramEngine()

    room_layout_engine = RoomLayoutEngine()

    geometry_engine = SpatialGeometryGenerator()

    wall_engine = WallGenerator()

    opening_engine = OpeningPlacementEngine()

    bim_engine = SemanticBIMMappingEngine()



    # ===============================================
    # PARKING SCENARIO
    # ===============================================


    parking_floor = floor_engine.generate(

        {
            "level":"B1",
            "type":"parking"
        }

    )


    parking_scenario = {


        "scenario":"parking",


        "requirements":

        [

            "car_lift",

            "ramp",

            "ventilation"

        ]

    }



    parking_result = scenario_adapter.apply(

        parking_floor,

        parking_scenario

    )



    print(
        "\n===== PARKING RESULT ====="
    )

    print(
        parking_result
    )



    # ===============================================
    # DUPLEX SCENARIO
    # ===============================================


    duplex_floor = floor_engine.generate(

        {
            "level":"F3",
            "type":"duplex",
            "units":2
        }

    )


    duplex_scenario = {


        "scenario":"duplex",


        "requirements":

        [

            "internal_stair",

            "double_height",

            "private_zone"

        ]

    }



    duplex_result = scenario_adapter.apply(

        duplex_floor,

        duplex_scenario

    )



    print(
        "\n===== DUPLEX RESULT ====="
    )

    print(
        duplex_result
    )



    # ===============================================
    # GEOMETRY CHECK
    # ===============================================


    room_program = room_program_engine.generate(

        {
            "type":
                "residential"
        }

    )


    room_layout = room_layout_engine.generate(

        room_program,

        {
            "id":
                "F3-U1"
        }

    )


    geometry = geometry_engine.generate(

        room_layout,

        {
            "id":
                "F3-U1"
        }

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



    semantic = bim_engine.generate(

        geometry["rooms"],

        walls["walls"],

        openings["openings"]

    )



    print(
        "\n===== BIM RESULT ====="
    )

    print(
        len(
            semantic["elements"]
        )
    )



    assert len(
        parking_result["spaces"]
    ) >= 4



    assert len(
        duplex_result["spaces"]
    ) >= 4



    assert len(
        semantic["elements"]
    ) > 0



    print(
        "\n✅ FULL SCENARIO INTELLIGENCE PIPELINE TEST PASSED"
    )



if __name__ == "__main__":

    test_full_scenario_intelligence_pipeline()