from core.bim.vertical_ifc_adapter import (
    VerticalIFCAdapter
)



def test_vertical_ifc_export_adapter():


    engine = VerticalIFCAdapter()



    semantic = {


        "semantic_elements":

        [

            {

                "semantic_type":
                    "escalator",

                "geometry":
                    [
                        [5,5],
                        [11,6]
                    ]

            },


            {

                "semantic_type":
                    "moving_ramp",

                "geometry":
                    [
                        [5,8],
                        [21,9]
                    ]

            },


            {

                "semantic_type":
                    "elevator",

                "geometry":
                    [
                        [10,10],
                        [14,14]
                    ]

            },


            {

                "semantic_type":
                    "stair",

                "geometry":
                    [
                        [0,10],
                        [4,14]
                    ]

            }

        ]

    }



    result = engine.convert_package(

        semantic

    )


    print(
        "\n===== IFC VERTICAL ELEMENTS ====="
    )


    print(result)



    classes = [

        x["ifc_class"]

        for x in result["elements"]

    ]



    assert "IfcTransportElement" in classes

    assert "IfcBuildingElementProxy" in classes

    assert "IfcStair" in classes



    print(
        "\n✅ VERTICAL IFC EXPORT ADAPTER TEST PASSED"
    )



if __name__ == "__main__":

    test_vertical_ifc_export_adapter()