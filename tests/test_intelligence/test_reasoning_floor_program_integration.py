from core.building.floor_program_engine import (
    FloorProgramEngine
)

from core.intelligence.reasoning_program_bridge import (
    ReasoningProgramBridge
)

from core.intelligence.floor_program_reasoning_adapter import (
    FloorProgramReasoningAdapter
)



def test_reasoning_floor_program_integration():


    bridge = ReasoningProgramBridge()

    adapter = FloorProgramReasoningAdapter()

    floor_engine = FloorProgramEngine()



    reasoning_result = {


        "decisions":

        [

            {
                "target":
                    "G",

                "function":
                    "commercial",

                "requirements":

                [
                    "frontage",
                    "mezzanine_possible"
                ]

            }

        ]

    }



    program_requirements = bridge.translate(

        reasoning_result

    )



    floor_input = adapter.adapt(

        {
            "level":
                "G",

            "type":
                "commercial"

        },

        program_requirements

    )



    floor_program = floor_engine.generate(

        floor_input,

        floor_input

    )



    print(
        "\n========== FLOOR PROGRAM RESULT =========="
    )

    print(
        floor_program
    )



    spaces = [

        space.get("type")

        for space in floor_program.get(
            "spaces",
            []
        )

    ]


    assert "mezzanine" in spaces


    print(
        "\n✅ REASONING FLOOR PROGRAM INTEGRATION TEST PASSED"
    )



if __name__ == "__main__":

    test_reasoning_floor_program_integration()