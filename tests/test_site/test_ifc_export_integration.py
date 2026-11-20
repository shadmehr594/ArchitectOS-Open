"""
ArchitectOS IFC Export Integration Test v1.0
"""


from core.bim.ifc_geometry_provider_adapter import (
    IFCGeometryProviderAdapter
)


def test_ifc_export_integration():


    provider = IFCGeometryProviderAdapter()



    ifc_input = {


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

                    0,

                    0

                ],

                "end":[

                    4,

                    0

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



    result = provider.generate(

        ifc_input

    )



    print(

        "\n========== EXPORT INPUT =========="

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



    assert entities[0].get(

        "entity"

    ) == "IfcSpace"



    assert entities[1].get(

        "entity"

    ) == "IfcWall"



    assert entities[2].get(

        "entity"

    ) == "IfcDoor"



    assert entities[3].get(

        "entity"

    ) == "IfcWindow"



    print(

        "\n✅ IFC EXPORT INTEGRATION TEST PASSED"

    )



if __name__ == "__main__":

    test_ifc_export_integration()