"""
ArchitectOS Adaptive Unit Generator Test v1.0
"""


from core.spatial.adaptive_unit_generator import (
    AdaptiveUnitGenerator
)



def test_adaptive_unit_generator():


    engine = AdaptiveUnitGenerator()



    unit = {


        "id":
            "A1",


        "unit_type":
            "2bed",


        "area":
            90,


        "bedrooms":
            2,


        "lightwell_access":
            True,


        "duct_required":
            True

    }



    result = engine.generate(

        unit

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    assert result.get(
        "area"
    ) == 90



    rooms = result.get(
        "rooms",
        []
    )


    assert len(
        rooms
    ) == 5



    bedroom_count = 0



    for room in rooms:


        if room["type"] == "bedroom":


            bedroom_count += 1


            assert room.get(
                "light_source"
            ) == "lightwell"



        if room["type"] == "kitchen":


            assert room.get(
                "ventilation"
            ) == "duct"



        if room["type"] == "bathroom":


            assert room.get(
                "ventilation"
            ) == "duct"



    assert bedroom_count == 2



    assert result.get(
        "type"
    ) == "2bed"



    print(
        "\n✅ ADAPTIVE UNIT GENERATOR TEST PASSED"
    )



if __name__ == "__main__":

    test_adaptive_unit_generator()