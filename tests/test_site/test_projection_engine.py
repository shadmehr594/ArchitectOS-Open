"""
ArchitectOS Projection Engine Test v1.0
"""


from core.spatial.projection_engine import (
    ProjectionEngine
)



def test_projection_engine():


    engine = ProjectionEngine()



    building = [

        [0,0],

        [20,0],

        [20,18],

        [0,18]

    ]



    projection = {


        "enabled":
            True,


        "side":
            "south",


        "width":
            8,


        "depth":
            1.5

    }



    result = engine.apply(

        {

            "level":
                "F2",


            "polygon":
                building

        },

        projection

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    polygon = result.get(
        "polygon",
        []
    )



    assert len(
        polygon
    ) == 4



    assert polygon[0] == [
        0,
        -1.5
    ]



    assert polygon[1] == [
        8,
        -1.5
    ]



    assert result["projection"]["side"] == "south"



    assert result["projection"]["width"] == 8



    assert result["projection"]["depth"] == 1.5



    print(
        "\n✅ PROJECTION ENGINE TEST PASSED"
    )



if __name__ == "__main__":

    test_projection_engine()