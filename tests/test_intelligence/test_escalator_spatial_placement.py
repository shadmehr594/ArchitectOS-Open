from core.spatial.escalator_spatial_placement_engine import (
    EscalatorSpatialPlacementEngine
)



def test_escalator_spatial_placement():


    engine = EscalatorSpatialPlacementEngine()



    escalator = {

        "type":"escalator",

        "length":6.4,

        "width":1.0

    }



    result = engine.place(

        escalator,

        origin=(5,5),

        location="atrium"

    )



    print(
        "\n===== ESCALATOR PLACEMENT ====="
    )


    print(result)



    assert result["system"]=="escalator"

    assert len(
        result["polygon"]
    ) == 4



    print(
        "\n✅ ESCALATOR SPATIAL PLACEMENT TEST PASSED"
    )



if __name__=="__main__":

    test_escalator_spatial_placement()