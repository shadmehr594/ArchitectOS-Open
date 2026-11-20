"""
ArchitectOS Building Form Solver v2.1 Test
"""


from core.site.building_form_solver_v21 import BuildingFormSolverV21



def test_building_form_v21():


    engine = BuildingFormSolverV21()



    site = {

        "width":20,

        "depth":30

    }



    buildable_polygons = [

        [

            [0,0],

            [20,0],

            [20,28.3],

            [0,28.3]

        ],

        [

            [7,28.3],

            [20,28.3],

            [20,30],

            [7,30]

        ]

    ]



    request = {

        "coverage":60,

        "placement":"north"

    }



    result = engine.solve(

        site,

        buildable_polygons,

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
        "coverage"
    ) <= 60



    assert len(

        footprint.get(

            "polygon",

            []

        )

    ) >= 4



    assert result["building"].get(
        "placement"
    ) == "north"



    print(
        "\n✅ BUILDING FORM SOLVER v2.1 TEST PASSED"
    )



if __name__ == "__main__":

    test_building_form_v21()