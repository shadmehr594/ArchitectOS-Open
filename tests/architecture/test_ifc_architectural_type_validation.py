"""
ArchitectOS IFC Type Validation
"""


import ifcopenshell


from core.architecture.bim.architectural_ifc_exporter_v2 import (
    ArchitecturalIFCExporterV2
)



def test_ifc_architectural_type_validation():


    geometry = {


        "spaces":[

            {
                "name":"Room",
                "floor":"F1",
                "height":3.2
            }

        ],


        "boundaries":[

            {
                "space":"Room",
                "floor":"F1"
            }

        ],


        "slabs":[

            {
                "space":"Room",
                "floor":"F1"
            }

        ],


        "openings":[

            {
                "space":"Room",
                "floor":"F1",
                "name":"Window"
            }

        ],


        "vertical_geometry":[]

    }



    path = (
        "exports/"
        "ArchitectOS_Type_Test.ifc"
    )


    ArchitecturalIFCExporterV2().export(
        geometry,
        path
    )


    model = ifcopenshell.open(
        path
    )


    wall_types = model.by_type(
        "IfcWallType"
    )

    slab_types = model.by_type(
        "IfcSlabType"
    )

    window_types = model.by_type(
        "IfcWindowType"
    )


    relations = model.by_type(
        "IfcRelDefinesByType"
    )


    print(
        "\nTYPE CHECK:"
    )


    print(
        "Wall Types:",
        len(wall_types)
    )

    print(
        "Slab Types:",
        len(slab_types)
    )

    print(
        "Window Types:",
        len(window_types)
    )

    print(
        "Type Relations:",
        len(relations)
    )


    assert len(wall_types) >= 1

    assert len(slab_types) >= 1

    assert len(window_types) >= 1

    assert len(relations) >= 1


    print(
        "\n✅ IFC TYPE VALIDATION PASSED"
    )