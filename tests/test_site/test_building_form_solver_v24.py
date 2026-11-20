"""
ArchitectOS Building Form Solver v2.4 Test
"""


from core.site.building_form_solver_v24 import BuildingFormSolverV24



def test_building_form_v24():


    engine = BuildingFormSolverV24()



    site = {

        "width":20,

        "depth":30

    }



    request = {

        "placement":"north",

        "coverage":60,

        "courtyard":{

            "enabled":True,

            "side":"north",

            "position":"west",

            "width":7,

            "depth":1.7

        }

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



    building = result.get(
        "building",
        {}
    )


    footprint = building.get(
        "footprint",
        {}
    )


    courtyard = result.get(
        "courtyard",
        {}
    )



    assert footprint.get(
        "area"
    ) == 360



    assert footprint.get(
        "coverage"
    ) == 60



    assert courtyard.get(
        "polygon"
    ) == [

        [0,28.3],

        [7,28.3],

        [7,30],

        [0,30]

    ]



    print(
        "\n✅ BUILDING FORM SOLVER v2.4 TEST PASSED"
    )



if __name__ == "__main__":

    test_building_form_v24()