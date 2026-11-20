"""
ArchitectOS IFC Containment Validation
"""


import ifcopenshell


from core.architecture.bim.architectural_ifc_exporter_v2 import (
    ArchitecturalIFCExporterV2
)



def test_ifc_architectural_containment_validation():


    geometry = {


        "spaces":[

            {
                "name":"MainRoom",
                "floor":"F1",
                "height":3.2
            }

        ],


        "boundaries":[

            {
                "space":"MainRoom",
                "floor":"F1"
            }

        ],


        "slabs":[

            {
                "space":"MainRoom",
                "floor":"F1"
            }

        ],


        "openings":[

            {
                "space":"MainRoom",
                "floor":"F1",
                "name":"Window"
            }

        ],


        "vertical_geometry":[]

    }



    path = (
        "exports/"
        "ArchitectOS_Containment_Test.ifc"
    )



    ArchitecturalIFCExporterV2().export(
        geometry,
        path
    )



    model = ifcopenshell.open(
        path
    )



    contained = model.by_type(
        "IfcRelContainedInSpatialStructure"
    )


    storeys = model.by_type(
        "IfcBuildingStorey"
    )


    print(
        "\nCONTAINMENT CHECK:"
    )


    print(
        "Storeys:",
        len(storeys)
    )


    print(
        "Containment Relations:",
        len(contained)
    )



    assert len(storeys) == 1

    assert len(contained) >= 1


    relation = contained[0]


    assert len(
        relation.RelatedElements
    ) >= 1



    print(
        "\n✅ IFC CONTAINMENT VALIDATION PASSED"
    )