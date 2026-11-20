from core.intelligence.vertical_circulation_network_engine import (
    VerticalCirculationNetworkEngine
)



def test_vertical_network():


    engine = VerticalCirculationNetworkEngine()



    result = engine.analyze(

        {

            "building_type":
                "shopping_center",

            "floors":
                6,

            "basement":
                2,

            "public_flow":
                "high",

            "parking":
                True

        }

    )


    print(
        "\n===== VERTICAL NETWORK ====="
    )


    print(result)



    types = [

        x["type"]

        for x in result["systems"]

    ]



    assert "escalator" in types

    assert "moving_ramp" in types

    assert "elevator" in types

    assert "vehicle_ramp" in types



    print(
        "\n✅ VERTICAL CIRCULATION NETWORK TEST PASSED"
    )



if __name__=="__main__":

    test_vertical_network()