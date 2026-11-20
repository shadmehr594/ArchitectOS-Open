from core.spatial.moving_ramp_spatial_placement_engine import (
    MovingRampSpatialPlacementEngine
)



def test_moving_ramp_spatial_placement():


    engine = MovingRampSpatialPlacementEngine()



    ramp = {


        "type":
            "moving_ramp",


        "length":
            32,


        "width":
            1.5

    }



    result = engine.place(

        ramp,

        origin=(5,5),

        location="mall_atrium",

        shape="L"

    )



    print(
        "\n===== MOVING RAMP PLACEMENT ====="
    )


    print(result)



    assert result["system"]=="moving_ramp"

    assert len(
        result["polygon"]
    ) >= 4



    print(
        "\n✅ MOVING RAMP SPATIAL PLACEMENT TEST PASSED"
    )



if __name__=="__main__":

    test_moving_ramp_spatial_placement()