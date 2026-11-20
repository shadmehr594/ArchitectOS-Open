from core.intelligence.architectural_reasoning_engine import (
    ArchitecturalReasoningEngine
)


def test_architectural_reasoning():


    engine = ArchitecturalReasoningEngine()


    result = engine.analyze(

        {
            "floors":

            [

                {
                    "level":"B1",
                    "type":"parking"
                },

                {
                    "level":"G",
                    "type":"commercial"
                },

                {
                    "level":"F3",
                    "type":"duplex"
                },

                {
                    "level":"PH",
                    "type":"penthouse"
                }

            ]

        }

    )


    print(result)


    assert len(
        result["decisions"]
    ) == 4


    print(
        "✅ ARCHITECTURAL REASONING TEST PASSED"
    )


if __name__ == "__main__":

    test_architectural_reasoning()