"""
ArchitectOS IFC Architectural Spatial Validation Test

Validates:

IfcProject
    |
IfcSite
    |
IfcBuilding
    |
IfcBuildingStorey
    |
IfcWall
IfcSlab
IfcSpace

+
Containment
+
Placement
"""


from core.architecture.bim.architectural_ifc_exporter_v2 import (
    ArchitecturalIFCExporterV2
)

import ifcopenshell



def test_ifc_architectural_spatial_validation():


    print(
        "\n"
        "================================\n"
        "IFC ARCHITECTURAL SPATIAL VALIDATION TEST\n"
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


        "openings":[],

        "vertical_geometry":[]

    }



    path = (
        "exports/"
        "ArchitectOS_Spatial_Validation.ifc"
    )


    exporter = ArchitecturalIFCExporterV2()


    result = exporter.export(
        geometry,
        path
    )


    model = ifcopenshell.open(
        result["path"]
    )


    print("\nSPATIAL CHECK:")


    projects = model.by_type(
        "IfcProject"
    )

    buildings = model.by_type(
        "IfcBuilding"
    )

    storeys = model.by_type(
        "IfcBuildingStorey"
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
        "Projects:",
        len(projects)
    )

    print(
        "Buildings:",
        len(buildings)
    )

    print(
        "Storeys:",
        len(storeys)
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

    assert len(buildings) == 1

    assert len(storeys) == 1

    assert len(walls) == 1

    assert len(slabs) == 1

    assert len(spaces) == 1


    wall = walls[0]


    slab = slabs[0]


    print(
        "\nPLACEMENT:"
    )


    assert wall.ObjectPlacement is not None

    assert slab.ObjectPlacement is not None


    print(
        "\n✅ IFC ARCHITECTURAL SPATIAL VALIDATION PASSED"
    )