from core.architecture.bim.ifc_geometry_intent_resolver import IFCGeometryIntentResolver



def test_ifc_geometry_intent_resolver_v1():


    print(
        "\n====== IFC GEOMETRY INTENT RESOLVER V1 ======"
    )


    resolver = IFCGeometryIntentResolver()



    ifc_mapping = {


        "ifc_elements": [


            {

                "ifc_class": "IfcWall",

                "name": "Facade Stone Wall",

                "level": "F1",

                "material": "travertine",

                "geometry": {

                    "height": 3.2,

                    "thickness": 0.35,

                    "alignment": "external"

                }

            },



            {

                "ifc_class": "IfcRoof",

                "name": "Classical Dome",

                "level": "Roof",

                "material": "stone",

                "geometry": {

                    "shape": "dome",

                    "position": "central_axis"

                }

            },



            {

                "ifc_class": "IfcColumn",

                "name": "classical_columns",

                "level": "F1",

                "material": "stone",

                "geometry": {

                    "shape": "classical_column",

                    "height": 3.2

                }

            },



            {

                "ifc_class": "IfcWindow",

                "name": "arched_openings",

                "level": "F1",

                "material": "stone",

                "geometry": {

                    "opening": True,

                    "style": "classical"

                }

            }


        ]

    }



    result = resolver.resolve(
        ifc_mapping
    )



    print(
        "\n====== GEOMETRY RESOLUTION RESULT ======"
    )


    print(
        result
    )



    elements = result["geometry_elements"]



    assert (
        len(elements)
        ==
        4
    )



    wall = None

    roof = None

    column = None

    window = None



    for element in elements:


        if element["ifc_class"] == "IfcWall":

            wall = element


        elif element["ifc_class"] == "IfcRoof":

            roof = element


        elif element["ifc_class"] == "IfcColumn":

            column = element


        elif element["ifc_class"] == "IfcWindow":

            window = element



    assert wall is not None


    assert (
        wall["geometry"]["geometry_type"]
        ==
        "extruded_wall"
    )


    assert (
        wall["geometry"]["height"]
        ==
        3.2
    )


    assert roof is not None


    assert (
        roof["geometry"]["geometry_type"]
        ==
        "dome"
    )


    assert (
        roof["geometry"]["radius"]
        ==
        5.0
    )


    assert (
        roof["geometry"]["height"]
        ==
        3.5
    )



    assert column is not None


    assert (
        column["geometry"]["geometry_type"]
        ==
        "column"
    )


    assert window is not None


    assert (
        window["geometry"]["geometry_type"]
        ==
        "opening"
    )



    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_ifc_geometry_intent_resolver_v1()