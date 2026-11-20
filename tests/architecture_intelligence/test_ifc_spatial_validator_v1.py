import os

import ifcopenshell

from core.bim.ifc_spatial_validator_v1 import IFCSpatialValidatorV1



def create_spatial_test_ifc():


    model = ifcopenshell.file(
        schema="IFC4"
    )


    # ==============================================
    # CONTEXT
    # ==============================================

    context = model.create_entity(
        "IfcGeometricRepresentationContext",
        ContextIdentifier="Model",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5
    )



    # ==============================================
    # SPATIAL STRUCTURE
    # ==============================================

    project = model.create_entity(
        "IfcProject",
        GlobalId=ifcopenshell.guid.new(),
        Name="ArchitectOS Spatial Test"
    )


    site = model.create_entity(
        "IfcSite",
        GlobalId=ifcopenshell.guid.new(),
        Name="Test Site"
    )


    building = model.create_entity(
        "IfcBuilding",
        GlobalId=ifcopenshell.guid.new(),
        Name="Test Building"
    )


    storey = model.create_entity(
        "IfcBuildingStorey",
        GlobalId=ifcopenshell.guid.new(),
        Name="F1",
        Elevation=0.0
    )



    # ==============================================
    # ELEMENTS
    # ==============================================

    wall = model.create_entity(
        "IfcWall",
        GlobalId=ifcopenshell.guid.new(),
        Name="Facade Stone Wall"
    )


    column = model.create_entity(
        "IfcColumn",
        GlobalId=ifcopenshell.guid.new(),
        Name="Classical Column"
    )


    window = model.create_entity(
        "IfcWindow",
        GlobalId=ifcopenshell.guid.new(),
        Name="Arched Window"
    )



    # ==============================================
    # SPATIAL RELATIONSHIPS
    # ==============================================

    model.create_entity(
        "IfcRelAggregates",
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=project,
        RelatedObjects=[
            site
        ]
    )


    model.create_entity(
        "IfcRelAggregates",
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=site,
        RelatedObjects=[
            building
        ]
    )


    model.create_entity(
        "IfcRelAggregates",
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=building,
        RelatedObjects=[
            storey
        ]
    )



    model.create_entity(
        "IfcRelContainedInSpatialStructure",
        GlobalId=ifcopenshell.guid.new(),
        RelatingStructure=storey,
        RelatedElements=[
            wall,
            column,
            window
        ]
    )



    return model





def test_ifc_spatial_validator_v1():


    print(
        "\n====== IFC SPATIAL VALIDATOR V1 ======"
    )



    model = create_spatial_test_ifc()



    os.makedirs(
        "exports",
        exist_ok=True
    )



    output_path = (
        "exports/"
        "test_spatial_validator.ifc"
    )



    model.write(
        output_path
    )



    validator = IFCSpatialValidatorV1()



    result = validator.validate(
        output_path
    )



    print(
        "\n====== SPATIAL VALIDATION RESULT ======"
    )


    print(
        result
    )



    assert (
        result["status"]
        ==
        "passed"
    )


    assert (
        result["checks"]["project"]
    )


    assert (
        result["checks"]["site"]
    )


    assert (
        result["checks"]["building"]
    )


    assert (
        result["checks"]["storeys"]
    )


    assert (
        result["checks"]["assignments"]
    )


    assert (
        result["spatial_health"]["score"]
        ==
        100
    )


    print(
        "\n====== TEST PASSED ======"
    )





if __name__ == "__main__":

    test_ifc_spatial_validator_v1()