from core.site.building_placement_engine import (
    BuildingPlacementEngine
)



def test_building_placement():


    engine = BuildingPlacementEngine()



    site = {

        "width":20,

        "depth":30,

        "road_side":"south"

    }



    request = {


        "coverage":60,


        "floors":5,


        "building_side":"south",


        "commercial_access":True,


        "residential_access":True,


        "parking_access":True


    }



    result = engine.generate(
        site,
        request
    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    assert result["coverage"] == 60

    assert len(
        result["access_points"]
    ) == 3



    print(
        "\n✅ Building Placement Engine TEST PASSED"
    )



if __name__ == "__main__":

    test_building_placement()