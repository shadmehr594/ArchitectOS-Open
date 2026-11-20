"""
ArchitectOS BIM Geometry Adapter Test v1.0
"""


from core.bim.bim_geometry_adapter import (
    BIMGeometryAdapter
)



def test_bim_geometry_adapter():


    engine = BIMGeometryAdapter()



    semantic_result = {


        "elements":[


            {

                "ifc_type":
                    "IfcSpace",

                "name":
                    "living",

                "zone":
                    "public",

                "geometry":[

                    [0,0],

                    [4,0],

                    [4,5],

                    [0,5]

                ]

            },


            {

                "ifc_type":
                    "IfcWall",

                "wall_type":
                    "interior",

                "thickness":
                    0.2,

                "boundary":[

                    [4,0],

                    [4,5]

                ]

            },


            {

                "ifc_type":
                    "IfcDoor",

                "room":
                    "living",

                "source":
                    "entrance"

            },


            {

                "ifc_type":
                    "IfcWindow",

                "room":
                    "living",

                "source":
                    "facade"

            }

        ]

    }



    result = engine.generate(

        semantic_result,

        "F1"

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    geometry_elements = result.get(
        "geometry_elements",
        []
    )



    assert len(
        geometry_elements
    ) == 4



    types = [

        element.get(
            "type"
        )

        for element in geometry_elements

    ]



    assert "IfcSpace" in types

    assert "IfcWall" in types

    assert "IfcDoor" in types

    assert "IfcWindow" in types



    space = geometry_elements[0]


    assert space.get(
        "level"
    ) == "F1"


    assert space.get(
        "height"
    ) == 3.2



    wall = geometry_elements[1]


    assert wall.get(
        "thickness"
    ) == 0.2


    assert wall.get(
        "height"
    ) == 3.2



    print(
        "\n✅ BIM GEOMETRY ADAPTER TEST PASSED"
    )



if __name__ == "__main__":

    test_bim_geometry_adapter()