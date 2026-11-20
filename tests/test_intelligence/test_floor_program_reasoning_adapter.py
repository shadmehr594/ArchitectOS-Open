from core.intelligence.floor_program_reasoning_adapter import (
    FloorProgramReasoningAdapter
)


def test_floor_program_reasoning_adapter():


    adapter = FloorProgramReasoningAdapter()


    result = adapter.adapt(

        {
            "level":"G",
            "type":"commercial"
        },


        {
            "program_requirements":

            [

                {
                    "target":"G",
                    "function":"commercial",
                    "additions":
                    [
                        "street_frontage",
                        "mezzanine"
                    ]
                }

            ]

        }

    )


    print(result)


    assert (
        "mezzanine"
        in
        result["reasoning_additions"]
    )


    assert (
        "street_frontage"
        in
        result["reasoning_additions"]
    )


    print(
        "✅ FLOOR PROGRAM REASONING ADAPTER TEST PASSED"
    )


if __name__ == "__main__":

    test_floor_program_reasoning_adapter()