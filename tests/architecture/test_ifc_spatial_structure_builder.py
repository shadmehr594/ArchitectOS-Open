"""
ArchitectOS IFC Spatial Structure Builder Test
"""


import ifcopenshell


from core.architecture.bim.ifc_spatial_structure_builder_v1 import (
    IFCSpatialStructureBuilderV1
)



def test_ifc_spatial_structure_builder():


    print(
        "\n"
        "================================\n"
        "IFC SPATIAL STRUCTURE BUILDER TEST\n"
        "================================\n"
    )


    model = ifcopenshell.file(
        schema="IFC4"
    )


    builder = IFCSpatialStructureBuilderV1(
        model
    )


    structure = builder.build()


    assert structure["project"].is_a(
        "IfcProject"
    )


    assert structure["site"].is_a(
        "IfcSite"
    )


    assert structure["building"].is_a(
        "IfcBuilding"
    )


    assert structure["storey"].is_a(
        "IfcBuildingStorey"
    )


    relations = model.by_type(
        "IfcRelAggregates"
    )


    assert len(relations) == 3


    print(
        "\n✅ IFC SPATIAL STRUCTURE BUILDER PASSED"
    )