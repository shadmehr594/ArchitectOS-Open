"""
ArchitectOS IFC Architectural Lifecycle Validation

Validates complete IFC semantic lifecycle.
"""


import ifcopenshell


from core.architecture.bim.architectural_ifc_exporter_v2 import (
    ArchitecturalIFCExporterV2
)



def test_ifc_architectural_lifecycle_validation():


    geometry = {


        "spaces":[

            {
                "name":"LivingRoom",
                "floor":"F1",
                "height":3.2
            }

        ],


        "boundaries":[

            {
                "space":"LivingRoom",
                "floor":"F1"
            }

        ],


        "slabs":[

            {
                "space":"LivingRoom",
                "floor":"F1"
            }

        ],


        "openings":[

            {
                "space":"LivingRoom",
                "floor":"F1",
                "name":"MainWindow",
                "type":"window"
            }

        ],


        "vertical_geometry":[]

    }



    path = (
        "exports/"
        "ArchitectOS_Lifecycle_Test.ifc"
    )



    ArchitecturalIFCExporterV2().export(
        geometry,
        path
    )



    model = ifcopenshell.open(
        path
    )



    # ===============================
    # CORE ENTITIES
    # ===============================

    projects = model.by_type(
        "IfcProject"
    )

    sites = model.by_type(
        "IfcSite"
    )

    buildings = model.by_type(
        "IfcBuilding"
    )

    storeys = model.by_type(
        "IfcBuildingStorey"
    )

    spaces = model.by_type(
        "IfcSpace"
    )

    walls = model.by_type(
        "IfcWall"
    )

    slabs = model.by_type(
        "IfcSlab"
    )

    windows = model.by_type(
        "IfcWindow"
    )


    # ===============================
    # RELATIONS
    # ===============================

    aggregates = model.by_type(
        "IfcRelAggregates"
    )


    contained = model.by_type(
        "IfcRelContainedInSpatialStructure"
    )


    boundaries = model.by_type(
        "IfcRelSpaceBoundary"
    )


    voids = model.by_type(
        "IfcRelVoidsElement"
    )


    fills = model.by_type(
        "IfcRelFillsElement"
    )


    materials = model.by_type(
        "IfcRelAssociatesMaterial"
    )


    properties = model.by_type(
        "IfcRelDefinesByProperties"
    )


    types = model.by_type(
        "IfcRelDefinesByType"
    )



    print(
        "\nLIFECYCLE CHECK:"
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
        "Spaces:",
        len(spaces)
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
        "Windows:",
        len(windows)
    )


    print(
        "Aggregates:",
        len(aggregates)
    )


    print(
        "Contained:",
        len(contained)
    )


    print(
        "Boundaries:",
        len(boundaries)
    )


    print(
        "Voids:",
        len(voids)
    )


    print(
        "Fills:",
        len(fills)
    )


    print(
        "Materials:",
        len(materials)
    )


    print(
        "Properties:",
        len(properties)
    )


    print(
        "Types:",
        len(types)
    )



    assert len(projects) == 1

    assert len(sites) == 1

    assert len(buildings) == 1

    assert len(storeys) == 1


    assert len(spaces) >= 1

    assert len(walls) >= 1

    assert len(slabs) >= 1

    assert len(windows) >= 1


    assert len(aggregates) >= 3

    assert len(contained) >= 1

    assert len(boundaries) >= 1

    assert len(voids) >= 1

    assert len(fills) >= 1

    assert len(materials) >= 1

    assert len(properties) >= 1

    assert len(types) >= 1



    print(
        "\n✅ IFC ARCHITECTURAL LIFECYCLE VALIDATION PASSED"
    )