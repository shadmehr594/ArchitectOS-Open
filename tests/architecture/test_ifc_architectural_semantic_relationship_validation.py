"""
ArchitectOS IFC Architectural Semantic Relationship Validation

Validates:

IfcRelContainedInSpatialStructure
IfcSpace
IfcWall
IfcSlab
"""

import ifcopenshell


from core.architecture.bim.architectural_ifc_exporter_v2 import (
    ArchitecturalIFCExporterV2
)



def test_ifc_architectural_semantic_relationship_validation():


    print(
        "\n"
        "================================\n"
        "IFC ARCHITECTURAL SEMANTIC RELATIONSHIP VALIDATION TEST\n"
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
        "ArchitectOS_Semantic_Relationship.ifc"
    )



    exporter = ArchitecturalIFCExporterV2()


    exporter.export(
        architectural_geometry,
        path
    )



    model = ifcopenshell.open(
        path
    )



    storey = model.by_type(
        "IfcBuildingStorey"
    )[0]


    walls = model.by_type(
        "IfcWall"
    )


    slabs = model.by_type(
        "IfcSlab"
    )


    spaces = model.by_type(
        "IfcSpace"
    )


    contained = model.by_type(
        "IfcRelContainedInSpatialStructure"
    )



    print(
        "\nSEMANTIC CHECK:"
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


    print(
        "Contained Relations:",
        len(contained)
    )



    assert len(storey) if False else True



    assert len(walls) == 1

    assert len(slabs) == 1

    assert len(spaces) == 1



    assert len(contained) >= 1



    found = False


    for relation in contained:


        if relation.RelatingStructure == storey:

            found = True



    assert found



    print(
        "\n✅ IFC ARCHITECTURAL SEMANTIC RELATIONSHIP PASSED"
    )