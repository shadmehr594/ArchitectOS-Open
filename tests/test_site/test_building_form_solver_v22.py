"""
ArchitectOS Building Form Solver v2.2 Test
"""


from core.site.building_form_solver_v22 import BuildingFormSolverV22



def test_building_form_v22():


    engine = BuildingFormSolverV22()



    site = {

        "width": 20,

        "depth": 30

    }



    polygon = [

        [0,0],

        [20,0],

        [20,28.3],

        [20,30],

        [7,30],

        [7,28.3],

        [0,28.3]

    ]



    request = {

        "placement": "north",

        "coverage": 60

    }



    result = engine.solve(

        site,

        polygon,

        request

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    footprint = result.get(
        "building",
        {}
    ).get(
        "footprint",
        {}
    )



    assert footprint.get(
        "area"
    ) == 360



    assert footprint.get(
        "coverage"
    ) <= 60



    assert len(
        footprint.get(
            "polygon",
            []
        )
    ) == 6



    assert result["building"].get(
        "placement"
    ) == "north"



    print(
        "\n✅ BUILDING FORM SOLVER v2.2 TEST PASSED"
    )



if __name__ == "__main__":

    test_building_form_v22()