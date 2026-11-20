from core.intelligence.architectural_intelligence_orchestrator import (
    ArchitecturalIntelligenceOrchestrator
)



def test_architectural_intelligence_orchestrator():


    engine = ArchitecturalIntelligenceOrchestrator()



    result = engine.analyze(

        {

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

    )



    print(
        "\n========== INTELLIGENCE RESULT =========="
    )

    print(result)



    assert "decisions" in result

    assert "program_requirements" in result

    assert "vertical_systems" in result

    assert isinstance(
        result["decisions"],
        list
    )


    assert isinstance(
        result["program_requirements"],
        list
    )


    assert isinstance(
        result["vertical_systems"],
        list
    )



    assert (

        len(

            result["vertical_systems"]

        )

        > 0

    )


    print(
        "✅ ARCHITECTURAL INTELLIGENCE ORCHESTRATOR TEST PASSED"
    )



if __name__ == "__main__":

    test_architectural_intelligence_orchestrator()