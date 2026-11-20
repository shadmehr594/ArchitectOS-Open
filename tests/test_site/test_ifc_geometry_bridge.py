"""
ArchitectOS IFC Geometry Bridge Test v1.0
"""


from core.bim.ifc_geometry_bridge import (
    IFCGeometryBridge
)



def test_ifc_geometry_bridge():


    engine = IFCGeometryBridge()



    geometry_result = {


        "geometry_elements":[


            {


                "type":
                    "IfcSpace",

                "level":
                    "F1",

                "polygon":[

                    [0,0],

                    [4,0],

                    [4,5],

                    [0,5]

                ],

                "height":
                    3.2

            },


            {


                "type":
                    "IfcWall",

                "level":
                    "F1",

                "start":[

                    4,

                    0

                ],

                "end":[

                    4,

                    5

                ],

                "height":
                    3.2,

                "thickness":
                    0.2

            },


            {


                "type":
                    "IfcDoor",

                "level":
                    "F1",

                "host_room":
                    "living"

            },


            {


                "type":
                    "IfcWindow",

                "level":
                    "F1",

                "host_room":
                    "living"

            }

        ]

    }



    result = engine.generate(

        geometry_result

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    inputs = result.get(
        "ifc_geometry_input",
        []
    )



    assert len(
        inputs
    ) == 4



    types = [

        item.get(
            "type"
        )

        for item in inputs

    ]



    assert "IfcSpace" in types

    assert "IfcWall" in types

    assert "IfcDoor" in types

    assert "IfcWindow" in types



    space = inputs[0]


    assert space.get(
        "level"
    ) == "F1"


    assert space.get(
        "height"
    ) == 3.2



    wall = inputs[1]


    assert wall.get(
        "thickness"
    ) == 0.2


    assert wall.get(
        "height"
    ) == 3.2



    print(
        "\n✅ IFC GEOMETRY BRIDGE TEST PASSED"
    )



if __name__ == "__main__":

    test_ifc_geometry_bridge()