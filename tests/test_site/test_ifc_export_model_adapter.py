"""
ArchitectOS IFC Export Model Adapter Test v1.0
"""


from core.bim.ifc_export_model_adapter import (
    IFCExportModelAdapter
)



def test_ifc_export_model_adapter():


    engine = IFCExportModelAdapter()



    input_data = {


        "ifc_entities":[


            {

                "entity":
                    "IfcSpace",

                "level":
                    "F1"

            },


            {

                "entity":
                    "IfcWall",

                "level":
                    "F1",

                "geometry":

                {

                    "height":
                        3.2

                }

            },


            {

                "entity":
                    "IfcDoor",

                "host":
                    "living",

                "level":
                    "F1"

            }

        ]

    }



    result = engine.convert(

        input_data

    )



    print(

        "\n========== RESULT =========="

    )


    print(

        result

    )



    elements = result.get(

        "bim_elements",

        []

    )



    assert len(

        elements

    ) == 3



    assert elements[0].get(
        "ifc_type"
    ) == "IfcSpace"



    assert elements[1].get(
        "ifc_type"
    ) == "IfcWall"



    assert elements[1].get(
        "geometry"
    ).get(
        "height"
    ) == 3.2



    assert elements[2].get(
        "ifc_type"
    ) == "IfcDoor"



    print(

        "\n✅ IFC EXPORT MODEL ADAPTER TEST PASSED"

    )



if __name__ == "__main__":

    test_ifc_export_model_adapter()