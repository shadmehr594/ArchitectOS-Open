"""
ArchitectOS Adaptive Residential Layout Engine Test v1.0
"""


from core.spatial.adaptive_residential_layout_engine import (
    AdaptiveResidentialLayoutEngine
)



def test_adaptive_residential_layout():


    engine = AdaptiveResidentialLayoutEngine()



    project = {


        "site_width":
            20,


        "site_depth":
            30,


        "floors":
            5,


        "units_per_floor":
            4,


        "coverage":
            100,


        "program":
            "residential",


        "separate_ducts":
            True

    }



    result = engine.generate(

        project

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    strategy = result.get(
        "strategy",
        {}
    )



    lightwells = strategy.get(
        "lightwells",
        {}
    )


    assert lightwells.get(
        "required"
    ) is True



    assert lightwells.get(
        "count"
    ) == 1



    ducts = strategy.get(
        "ducts",
        {}
    )


    assert ducts.get(
        "bathroom"
    ) == "independent"



    assert ducts.get(
        "kitchen"
    ) == "independent"



    core = strategy.get(
        "core",
        {}
    )


    assert core.get(
        "type"
    ) == "central"



    print(
        "\n✅ ADAPTIVE RESIDENTIAL LAYOUT TEST PASSED"
    )



if __name__ == "__main__":

    test_adaptive_residential_layout()