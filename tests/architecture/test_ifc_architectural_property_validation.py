"""
ArchitectOS IFC Property Validation
"""


import ifcopenshell


from core.architecture.bim.architectural_ifc_exporter_v2 import (
    ArchitecturalIFCExporterV2
)



def test_ifc_architectural_property_validation():


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
                "name":"Window",
                "type":"window"
            }

        ],


        "vertical_geometry":[]

    }



    path = (
        "exports/"
        "ArchitectOS_Property_Test.ifc"
    )


    ArchitecturalIFCExporterV2().export(
        geometry,
        path
    )


    model = ifcopenshell.open(
        path
    )


    property_sets = model.by_type(
        "IfcPropertySet"
    )


    relations = model.by_type(
        "IfcRelDefinesByProperties"
    )


    print(
        "\nPROPERTY CHECK:"
    )


    print(
        "Property Sets:",
        len(property_sets)
    )


    print(
        "Property Relations:",
        len(relations)
    )


    assert len(property_sets) >= 2

    assert len(relations) >= 2


    print(
        "\n✅ IFC PROPERTY VALIDATION PASSED"
    )