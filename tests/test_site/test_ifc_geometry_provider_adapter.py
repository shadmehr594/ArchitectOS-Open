"""
ArchitectOS IFC Geometry Provider Adapter Test v1.0
"""


from core.bim.ifc_geometry_provider_adapter import (
    IFCGeometryProviderAdapter
)



def test_ifc_geometry_provider_adapter():


    engine = IFCGeometryProviderAdapter()



    bridge_result = {


        "ifc_geometry_input":[


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

        bridge_result

    )



    print(
        "\n========== RESULT =========="
    )


    print(
        result
    )



    entities = result.get(
        "ifc_entities",
        []
    )



    assert len(
        entities
    ) == 4



    types = [

        entity.get(
            "entity"
        )

        for entity in entities

    ]



    assert "IfcSpace" in types

    assert "IfcWall" in types

    assert "IfcDoor" in types

    assert "IfcWindow" in types



    wall = entities[1]


    assert wall.get(
        "level"
    ) == "F1"


    assert wall.get(
        "geometry"
    ).get(
        "height"
    ) == 3.2



    print(
        "\n✅ IFC GEOMETRY PROVIDER ADAPTER TEST PASSED"
    )



if __name__ == "__main__":

    test_ifc_geometry_provider_adapter()