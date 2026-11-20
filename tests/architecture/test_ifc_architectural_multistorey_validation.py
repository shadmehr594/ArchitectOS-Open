"""
ArchitectOS IFC Architectural Multi Storey Validation
"""

import ifcopenshell

from core.architecture.bim.architectural_ifc_exporter_v2 import (
    ArchitecturalIFCExporterV2
)


def test_ifc_architectural_multistorey_validation():

    geometry = {

        "spaces": [

            {
                "name": "Living_F1",
                "floor": "F1",
                "height": 3.2
            },

            {
                "name": "Office_F2",
                "floor": "F2",
                "height": 3.2
            },

            {
                "name": "RoofTerrace_F3",
                "floor": "F3",
                "height": 3.2
            }

        ],


        "boundaries": [

            {
                "space": "Living_F1",
                "floor": "F1"
            },

            {
                "space": "Office_F2",
                "floor": "F2"
            }

        ],


        "slabs": [

            {
                "space": "Living_F1",
                "floor": "F1"
            },

            {
                "space": "Office_F2",
                "floor": "F2"
            },

            {
                "space": "RoofTerrace_F3",
                "floor": "F3"
            }

        ],


        "openings": [

            {
                "space": "Living_F1",
                "floor": "F1",
                "name": "Window_F1",
                "type": "window"
            },


            {
                "space": "Office_F2",
                "floor": "F2",
                "name": "Window_F2",
                "type": "window"
            }

        ],


        "vertical_geometry": []

    }


    path = (
        "exports/"
        "ArchitectOS_MultiStorey_Test.ifc"
    )


    ArchitecturalIFCExporterV2().export(
        geometry,
        path
    )


    model = ifcopenshell.open(path)


    storeys = model.by_type(
        "IfcBuildingStorey"
    )

    spaces = model.by_type(
        "IfcSpace"
    )

    contained = model.by_type(
        "IfcRelContainedInSpatialStructure"
    )


    print("\nMULTISTOREY CHECK:")

    print(
        "Storeys:",
        len(storeys)
    )

    print(
        "Spaces:",
        len(spaces)
    )

    print(
        "Contained:",
        len(contained)
    )


    assert len(storeys) == 3

    assert len(spaces) >= 3

    assert len(contained) >= 3


    names = [
        s.Name
        for s in storeys
    ]


    print(
        "Storey Names:",
        names
    )


    print(
        "\n✅ IFC MULTISTOREY VALIDATION PASSED"
    )