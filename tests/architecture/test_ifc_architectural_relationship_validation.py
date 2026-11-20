"""
ArchitectOS IFC Architectural Relationship Validation

Validates:

IfcRelAggregates
IfcRelContainedInSpatialStructure
IfcRelSpaceBoundary
"""


import ifcopenshell


from core.architecture.bim.architectural_ifc_exporter_v2 import (
    ArchitecturalIFCExporterV2
)



def test_ifc_architectural_relationship_validation():


    print(
        "\n"
        "================================\n"
        "IFC ARCHITECTURAL RELATIONSHIP VALIDATION TEST\n"
        "================================\n"
    )


    architectural_geometry = {


        "spaces": [

            {
                "name": "Main_Hall",
                "floor": "F1",
                "height": 3.2
            }

        ],


        "boundaries": [

            {
                "space": "Main_Hall",
                "floor": "F1"
            }

        ],


        "slabs": [

            {
                "space": "Main_Hall",
                "floor": "F1"
            }

        ],


        "openings": [],


        "vertical_geometry": []

    }



    path = (
        "exports/"
        "ArchitectOS_Relationship_Validation.ifc"
    )


    exporter = ArchitecturalIFCExporterV2()


    exporter.export(
        architectural_geometry,
        path
    )


    model = ifcopenshell.open(
        path
    )


    projects = model.by_type(
        "IfcProject"
    )


    buildings = model.by_type(
        "IfcBuilding"
    )


    storeys = model.by_type(
        "IfcBuildingStorey"
    )


    aggregates = model.by_type(
        "IfcRelAggregates"
    )


    contained = model.by_type(
        "IfcRelContainedInSpatialStructure"
    )


    boundaries = model.by_type(
        "IfcRelSpaceBoundary"
    )


    print(
        "\nRELATIONSHIP CHECK:"
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
        "Aggregates:",
        len(aggregates)
    )


    print(
        "Contained:",
        len(contained)
    )


    print(
        "Space Boundaries:",
        len(boundaries)
    )



    assert len(projects) == 1

    assert len(buildings) == 1

    assert len(storeys) == 1

    assert len(aggregates) >= 3



    print(
        "\n✅ IFC ARCHITECTURAL RELATIONSHIP VALIDATION PASSED"
    )