"""
ArchitectOS IFC Spatial Containment Test V1

IFC Spatial Structure:

IfcBuildingStorey
        |
        v
IfcRelContainedInSpatialStructure
        |
        v
IfcWall / IfcSlab
"""


import ifcopenshell


from core.architecture.bim.ifc_spatial_containment_v1 import (
    IFCSpatialContainmentV1
)



def test_ifc_spatial_containment():


    print(
        "\n"
        "================================\n"
        "IFC SPATIAL CONTAINMENT TEST\n"
        "================================\n"
    )



    # ==================================
    # IFC MODEL
    # ==================================

    model = ifcopenshell.file(
        schema="IFC4"
    )



    # ==================================
    # STOREY
    # ==================================

    storey = model.create_entity(

        "IfcBuildingStorey",

        GlobalId=ifcopenshell.guid.new(),

        Name="F1"

    )



    # ==================================
    # ELEMENTS
    # ==================================

    wall = model.create_entity(

        "IfcWall",

        GlobalId=ifcopenshell.guid.new(),

        Name="Main_Hall_Wall"

    )



    slab = model.create_entity(

        "IfcSlab",

        GlobalId=ifcopenshell.guid.new(),

        Name="Main_Hall_Slab"

    )



    elements = [

        wall,

        slab

    ]



    # ==================================
    # CONTAINMENT
    # ==================================

    containment = IFCSpatialContainmentV1(
        model
    )



    relation = containment.contain(

        storey,

        elements

    )



    assert relation is not None



    assert (

        relation.is_a()

        ==

        "IfcRelContainedInSpatialStructure"

    )



    assert (

        relation.RelatingStructure

        ==

        storey

    )



    assert (

        len(

            relation.RelatedElements

        )

        ==

        2

    )



    print(

        "\n✅ IFC SPATIAL CONTAINMENT PASSED"

    )