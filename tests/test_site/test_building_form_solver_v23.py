"""
ArchitectOS Building Form Solver v2.3 Test
"""


from core.site.building_form_solver_v23 import BuildingFormSolverV23



def test_building_form_v23():


    engine = BuildingFormSolverV23()



    site = {

        "width":20,

        "depth":30

    }



    request = {

        "placement":"north",

        "coverage":60

    }



    result = engine.solve(

        site,

        request

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    footprint = result["building"]["footprint"]



    assert footprint.get(
        "area"
    ) == 360



    assert footprint.get(
        "coverage"
    ) == 60



    assert footprint.get(
        "polygon"
    ) == [

        [0,12],

        [20,12],

        [20,30],

        [0,30]

    ]



    assert result["building"].get(
        "placement"
    ) == "north"



    print(
        "\n✅ BUILDING FORM SOLVER v2.3 TEST PASSED"
    )



if __name__ == "__main__":

    test_building_form_v23()