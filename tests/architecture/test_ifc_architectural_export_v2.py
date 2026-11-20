"""
ArchitectOS Architectural IFC Exporter V2 Test
"""

import os
import ifcopenshell


from core.architecture.bim.architectural_ifc_exporter_v2 import (
    ArchitecturalIFCExporterV2
)



def test_ifc_architectural_export_v2():


    print(
        "\n"
        "================================\n"
        "IFC ARCHITECTURAL EXPORT V2 TEST\n"
        "================================\n"
    )


    architectural_geometry = {


        "spaces": [

            {
                "name": "Main_Hall",
                "floor": "F1",
                "type": "room_volume",
                "height": 3.2
            }

        ],


        "boundaries": [

            {
                "space": "Main_Hall",
                "floor": "F1",
                "type": "wall_boundary"
            }

        ],


        "slabs": [

            {
                "space": "Main_Hall",
                "floor": "F1",
                "type": "floor_slab"
            }

        ],


        "openings": [],


        "vertical_geometry": []

    }



    path = (
        "exports/"
        "ArchitectOS_Architectural_V2.ifc"
    )


    exporter = ArchitecturalIFCExporterV2()


    result = exporter.export(
        architectural_geometry,
        path
    )


    assert os.path.exists(
        path
    )


    model = ifcopenshell.open(
        path
    )


    projects = model.by_type(
        "IfcProject"
    )


    walls = model.by_type(
        "IfcWall"
    )


    slabs = model.by_type(
        "IfcSlab"
    )


    spaces = model.by_type(
        "IfcSpace"
    )


    print(
        "\nIFC VALIDATION:"
    )

    print(
        "Projects:",
        len(projects)
    )

    print(
        "Walls:",
        len(walls)
    )

    print(
        "Slabs:",
        len(slabs)
    )

    print(
        "Spaces:",
        len(spaces)
    )


    assert len(projects) == 1

    assert len(walls) > 0

    assert len(slabs) > 0

    assert len(spaces) > 0


    print(
        "\n✅ ARCHITECTURAL IFC EXPORT V2 PASSED"
    )