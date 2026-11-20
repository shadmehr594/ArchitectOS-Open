from core.intelligence.intelligent_ramp_design_engine import (
    IntelligentRampDesignEngine
)



def test_intelligent_ramp_design():


    engine = IntelligentRampDesignEngine()



    accessible = engine.design(

        "accessible",

        {
            "height":0.8,
            "slope":8
        }

    )


    print(
        "\n===== ACCESSIBLE ====="
    )

    print(
        accessible
    )



    vehicle = engine.design(

        "vehicle",

        {
            "height":3,
            "parking_size":"large"
        }

    )


    print(
        "\n===== VEHICLE ====="
    )

    print(
        vehicle
    )



    override = engine.design(

        "vehicle",

        {
            "height":3,
            "slope":17,
            "shape":"L",
            "entry_exit":"separate"
        }

    )


    print(
        "\n===== OVERRIDE ====="
    )

    print(
        override
    )



    assert accessible["slope"] == 8

    assert vehicle["entry_exit"] == "separate"

    assert override["slope"] == 17

    assert override["shape"] == "L"


    print(
        "\n✅ INTELLIGENT RAMP DESIGN TEST PASSED"
    )



if __name__ == "__main__":

    test_intelligent_ramp_design()