from core.intelligence.escalator_design_engine import (
    EscalatorDesignEngine
)



def test_escalator_design():


    engine = EscalatorDesignEngine()



    result = engine.design(

        height=3.2

    )


    print(
        "\n===== ESCALATOR ====="
    )

    print(result)



    override = engine.design(

        height=4,

        override={

            "width":1.2,

            "angle":35

        }

    )


    print(
        "\n===== OVERRIDE ====="
    )

    print(override)



    assert result["type"] == "escalator"

    assert result["length"] > 0



    print(
        "\n✅ ESCALATOR DESIGN TEST PASSED"
    )



if __name__ == "__main__":

    test_escalator_design()