"""
ArchitectOS Building Form Solver v2 Test
"""


from core.site.building_form_solver_v2 import BuildingFormSolverV2



def test_building_form_v2():


    engine = BuildingFormSolverV2()



    site = {

        "width":20,

        "depth":30

    }



    buildable = [

        [

            [0,0],

            [20,0],

            [20,28.3],

            [0,28.3]

        ]

    ]



    request = {

        "coverage":60,

        "placement":"north"

    }



    result = engine.solve(

        site,

        buildable,

        request

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )


    assert result["building"]["footprint"]["coverage"] <= 60



    assert len(

        result["building"]["footprint"]["polygon"]

    ) == 4



    print(

        "\n✅ BUILDING FORM SOLVER V2 TEST PASSED"

    )



if __name__ == "__main__":

    test_building_form_v2()