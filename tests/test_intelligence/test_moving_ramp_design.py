from core.intelligence.moving_ramp_design_engine import (
    MovingRampDesignEngine
)



def test_moving_ramp_design():


    engine = MovingRampDesignEngine()



    result = engine.design(

        height=3.2

    )


    print(
        "\n===== MOVING RAMP ====="
    )


    print(result)



    override = engine.design(

        height=3.2,

        override={

            "slope":8,

            "width":1.8,

            "shopping_cart":True

        }

    )


    print(
        "\n===== OVERRIDE ====="
    )


    print(override)



    assert result["type"]=="moving_ramp"

    assert result["length"] > 0



    print(
        "\n✅ MOVING RAMP DESIGN TEST PASSED"
    )



if __name__=="__main__":

    test_moving_ramp_design()