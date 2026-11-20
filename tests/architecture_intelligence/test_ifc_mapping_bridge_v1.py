from core.architecture.bim.ifc_mapping_bridge import IFCMappingBridge



def test_ifc_mapping_bridge_v1():


    print(
        "\n====== IFC MAPPING BRIDGE V1 ======"
    )


    bridge = IFCMappingBridge()



    bim_enriched = {


        "bim_elements": [


            {

                "type": "IfcWall",

                "name": "Facade Stone Wall",

                "level": "F1",

                "material_layer": [

                    {

                        "material": "travertine",

                        "role": "finish"

                    }

                ],

                "geometry_intent": {

                    "height": 3.2,

                    "thickness": 0.35,

                    "alignment": "external"

                }

            },



            {

                "type": "IfcRoof",

                "name": "Classical Dome",

                "level": "Roof",

                "material_layer": [

                    {

                        "material": "stone",

                        "role": "finish"

                    }

                ],

                "geometry_intent": {

                    "shape": "dome",

                    "position": "central_axis"

                }

            },



            {

                "type": "IfcColumn",

                "name": "classical_columns",

                "level": "F1",

                "material_layer": [

                    {

                        "material": "stone",

                        "role": "finish"

                    }

                ],

                "geometry_intent": {

                    "shape": "classical_column",

                    "height": 3.2

                }

            },



            {

                "type": "IfcWall",

                "name": "Boundary Wall",

                "level": "Site",

                "material_layer": [

                    {

                        "material": "travertine",

                        "role": "finish"

                    }

                ],

                "geometry_intent": {

                    "height": 3.2,

                    "thickness": 0.35

                }

            }


        ]

    }



    result = bridge.map(
        bim_enriched
    )



    print(
        "\n====== IFC MAPPING RESULT ======"
    )


    print(
        result
    )



    elements = result["ifc_elements"]



    assert (
        len(elements)
        ==
        4
    )



    wall = None

    roof = None

    boundary = None



    for element in elements:


        if (
            element["name"]
            ==
            "Facade Stone Wall"
        ):

            wall = element



        if (
            element["name"]
            ==
            "Classical Dome"
        ):

            roof = element



        if (
            element["name"]
            ==
            "Boundary Wall"
        ):

            boundary = element



    assert wall is not None


    assert (
        wall["ifc_class"]
        ==
        "IfcWall"
    )


    assert (
        wall["material"]
        ==
        "travertine"
    )


    assert (
        wall["metadata"]["architectural_role"]
        ==
        "wall"
    )



    assert roof is not None


    assert (
        roof["ifc_class"]
        ==
        "IfcRoof"
    )


    assert (
        roof["metadata"]["architectural_role"]
        ==
        "roof"
    )


    assert boundary is not None


    assert (
        boundary["metadata"]["architectural_role"]
        ==
        "site_boundary"
    )



    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_ifc_mapping_bridge_v1()