"""
ArchitectOS Building Form Solver Test v1.0
"""


from core.site.building_form_solver import BuildingFormSolver



def test_building_form():


    engine = BuildingFormSolver()



    site = {


        "width": 20,


        "depth": 30


    }



    requirement = {


        "coverage": 60,


        "placement_side": "north",



        "courtyard": {


            "enabled": True,


            "side": "north",


            "area": 12,


            "depth": 1.7


        },



        "length_compensation": {


            "enabled": True,


            "extra_length": 1.2

        },



        "projection": {


            "enabled": True,


            "side": "south",


            "depth": 1.2


        }


    }



    result = engine.solve(


        site,


        requirement


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



    projection = building.get(

        "projection",

        {}

    )



    # ----------------------------------
    # CHECK COVERAGE
    # ----------------------------------

    assert footprint.get(

        "coverage"

    ) <= 60



    # ----------------------------------
    # CHECK POLYGON
    # ----------------------------------

    assert len(

        footprint.get(

            "polygon",

            []

        )

    ) == 4



    # ----------------------------------
    # CHECK PLACEMENT
    # ----------------------------------

    assert building.get(

        "placement"

    ) == "north"



    # ----------------------------------
    # CHECK PROJECTION
    # ----------------------------------

    assert projection.get(

        "enabled"

    ) is True



    assert projection.get(

        "side"

    ) == "south"



    print(

        "\n✅ Building Form Solver TEST PASSED"

    )



if __name__ == "__main__":


    test_building_form()