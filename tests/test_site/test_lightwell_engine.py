"""
ArchitectOS Lightwell Engine Test v1.0
"""


from core.site.lightwell_engine import LightwellEngine



def test_lightwell_engine():


    engine = LightwellEngine()



    building = {

        "area":600

    }



    floors = [

        {

            "name":"G",

            "usage":"commercial",

            "units":0

        },


        {

            "name":"F1",

            "usage":"residential",

            "units":4

        },


        {

            "name":"F2",

            "usage":"residential",

            "units":8

        }

    ]



    result = engine.generate(

        building,

        floors

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    lightwells = result.get(
        "lightwells",
        []
    )



    assert lightwells[0].get(
        "required"
    ) is False



    assert lightwells[1].get(
        "required"
    ) is True


    assert lightwells[1].get(
        "count"
    ) == 1



    assert lightwells[1].get(
        "width"
    ) == 3



    assert lightwells[1].get(
        "area"
    ) == 12



    assert lightwells[1].get(
        "access"
    ) == "corridor"



    assert lightwells[2].get(
        "count"
    ) == 2



    print(
        "\n✅ LIGHTWELL ENGINE TEST PASSED"
    )



if __name__ == "__main__":

    test_lightwell_engine()