"""
ArchitectOS Courtyard Engine v3 Test
"""


from core.site.courtyard_engine import CourtyardEngine



def test_courtyard():


    engine = CourtyardEngine()



    site = {

        "width":20,

        "depth":30

    }



    requirement = {

        "enabled": True,

        "side":"north",

        "position":"west",

        "width":7,

        "depth":1.7

    }



    result = engine.generate(

        site,

        requirement

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    courtyard = result.get(
        "courtyard",
        {}
    )



    assert courtyard.get(
        "side"
    ) == "north"



    assert courtyard.get(
        "position"
    ) == "west"



    assert courtyard.get(
        "area"
    ) >= 11.5



    assert len(
        courtyard.get(
            "polygon",
            []
        )
    ) == 4



    print(
        "\n✅ Courtyard Engine v3 TEST PASSED"
    )



if __name__ == "__main__":

    test_courtyard()