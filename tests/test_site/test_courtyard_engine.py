"""
ArchitectOS Courtyard Engine Test v1.0
"""


from core.site.courtyard_engine import CourtyardEngine



def test_courtyard():

    engine = CourtyardEngine()


    site = {

        "width": 20,

        "depth": 30

    }


    requirement = {

        "area": 12,

        "depth": 1.7,

        "side": "north"

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
        "area"
    ) >= 11.5


    assert len(
        courtyard.get(
            "polygon",
            []
        )
    ) == 4


    print(
        "\n✅ Courtyard Engine TEST PASSED"
    )



if __name__ == "__main__":

    test_courtyard()