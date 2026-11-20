"""
ArchitectOS IFC Architectural Opening Validation
"""


import ifcopenshell


from core.architecture.bim.architectural_ifc_exporter_v2 import (
    ArchitecturalIFCExporterV2
)



def test_ifc_architectural_opening_validation():


    print(
        "\n"
        "================================\n"
        "IFC ARCHITECTURAL OPENING VALIDATION TEST\n"
        "================================\n"
    )


    geometry = {


        "spaces":[

            {
                "name":"Main_Hall",
                "floor":"F1",
                "height":3.2
            }

        ],


        "boundaries":[

            {
                "space":"Main_Hall",
                "floor":"F1"
            }

        ],


        "slabs":[

            {
                "space":"Main_Hall",
                "floor":"F1"
            }

        ],


        "openings":[

            {
                "space":"Main_Hall",
                "floor":"F1",
                "type":"window",
                "name":"Main_Window"
            }

        ],


        "vertical_geometry":[]

    }



    path = (
        "exports/"
        "ArchitectOS_Opening_Test.ifc"
    )


    exporter = ArchitecturalIFCExporterV2()


    exporter.export(
        geometry,
        path
    )



    model = ifcopenshell.open(
        path
    )



    walls = model.by_type(
        "IfcWall"
    )


    windows = model.by_type(
        "IfcWindow"
    )


    opening_elements = model.by_type(
        "IfcOpeningElement"
    )


    voids = model.by_type(
        "IfcRelVoidsElement"
    )


    fills = model.by_type(
        "IfcRelFillsElement"
    )



    print(
        "\nOPENING CHECK:"
    )


    print(
        "Walls:",
        len(walls)
    )


    print(
        "Windows:",
        len(windows)
    )


    print(
        "Opening Elements:",
        len(opening_elements)
    )


    print(
        "Voids:",
        len(voids)
    )


    print(
        "Fills:",
        len(fills)
    )



    assert len(walls) == 1

    assert len(windows) == 1

    assert len(opening_elements) >= 1

    assert len(voids) >= 1

    assert len(fills) >= 1



    print(
        "\n✅ IFC OPENING VALIDATION PASSED"
    )