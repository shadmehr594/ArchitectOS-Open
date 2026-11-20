from core.intelligence.reasoning_program_bridge import (
    ReasoningProgramBridge
)


def test_reasoning_program_bridge():


    bridge = ReasoningProgramBridge()


    result = bridge.translate(

        {
            "decisions":

            [

                {
                    "target":"G",
                    "function":"commercial",
                    "requirements":
                    [
                        "frontage",
                        "mezzanine_possible"
                    ]
                },

                {
                    "target":"PH",
                    "function":"penthouse",
                    "requirements":
                    [
                        "terrace",
                        "large_openings"
                    ]
                }

            ]
        }

    )


    print(result)


    assert len(
        result["program_requirements"]
    ) == 2


    assert (
        "mezzanine"
        in
        result["program_requirements"][0]["additions"]
    )


    assert (
        "private_terrace"
        in
        result["program_requirements"][1]["additions"]
    )


    print(
        "✅ REASONING PROGRAM BRIDGE TEST PASSED"
    )


if __name__ == "__main__":

    test_reasoning_program_bridge()