"""
ArchitectOS Architectural IFC Geometry Validation Test

Validates:

IfcProject
 |
IfcSpace
 |
IfcWall
 |
IfcSlab
 |
Geometry Representation
 |
Placement
"""

import os
import ifcopenshell


from core.architecture.bim.architectural_ifc_exporter_v2 import (
    ArchitecturalIFCExporterV2
)



def test_ifc_architectural_geometry_validation():


    print(
        "\n"
        "================================\n"
        "IFC ARCHITECTURAL GEOMETRY VALIDATION TEST\n"
        "================================\n"
    )


    geometry = {


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
        "ArchitectOS_Geometry_Validation.ifc"
    )


    exporter = ArchitecturalIFCExporterV2()


    exporter.export(
        geometry,
        path
    )


    assert os.path.exists(
        path
    )


    model = ifcopenshell.open(
        path
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
        "\nGEOMETRY CHECK:"
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



    assert len(walls) == 1

    assert len(slabs) == 1

    assert len(spaces) == 1



    wall = walls[0]

    slab = slabs[0]


    print(
        "\nWALL REPRESENTATION:"
    )

    print(
        wall.Representation
    )


    print(
        "\nSLAB REPRESENTATION:"
    )

    print(
        slab.Representation
    )


    assert wall.Representation is not None

    assert slab.Representation is not None



    print(
        "\nPLACEMENT CHECK:"
    )


    assert wall.ObjectPlacement is not None

    assert slab.ObjectPlacement is not None



    print(
        "\n✅ IFC ARCHITECTURAL GEOMETRY VALIDATION PASSED"
    )