import os
import ifcopenshell

from core.bim.ifc_quality_validator_v2 import IFCQualityValidatorV2
from core.bim.geometry.ifc_geometry_provider import IFCGeometryProvider



def create_test_ifc():

    model = ifcopenshell.file(
        schema="IFC4"
    )


    context = model.create_entity(
        "IfcGeometricRepresentationContext",
        ContextIdentifier="Model",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5
    )


    origin = model.create_entity(
    "IfcCartesianPoint",
    Coordinates=(0.0,0.0,0.0)
    )


    axis2placement = model.create_entity(
        "IfcAxis2Placement3D",
        Location=origin
    )


    wall_placement = model.create_entity(
        "IfcLocalPlacement",
        RelativePlacement=axis2placement
    )


    column_placement = model.create_entity(
        "IfcLocalPlacement",
        RelativePlacement=axis2placement
    )


    window_placement = model.create_entity(
        "IfcLocalPlacement",
        RelativePlacement=axis2placement
    )


    project = model.create_entity(
        "IfcProject",
        GlobalId=ifcopenshell.guid.new(),
        Name="ArchitectOS Quality Test"
    )


    building = model.create_entity(
        "IfcBuilding",
        GlobalId=ifcopenshell.guid.new(),
        Name="Test Building"
    )


    storey = model.create_entity(
        "IfcBuildingStorey",
        GlobalId=ifcopenshell.guid.new(),
        Name="F1"
    )


    provider = IFCGeometryProvider(
        model,
        None,
        context
    )


    wall_shape = provider.create_wall_geometry(
        {
            "name": "Facade Stone Wall",
            "length": 20.0,
            "height": 3.2,
            "thickness": 0.35
        }
    )


    column_shape = provider.create_column_geometry(
        {
            "name": "Classical Column",
            "profile": "classical",
            "height": 3.2,
            "width": 0.5,
            "depth": 0.5
        }
    )


    window_shape = provider.create_window_geometry(
        {
            "name": "Arched Window",
            "width": 1.5,
            "height": 2.2,
            "thickness": 0.2
        }
    )


    wall = model.create_entity(
        "IfcWall",
        GlobalId=ifcopenshell.guid.new(),
        Name="Facade Stone Wall",
        Representation=wall_shape,
        ObjectPlacement=wall_placement
    )


    column = model.create_entity(
        "IfcColumn",
        GlobalId=ifcopenshell.guid.new(),
        Name="Classical Column",
        Representation=column_shape,
        ObjectPlacement=column_placement
    )


    window = model.create_entity(
        "IfcWindow",
        GlobalId=ifcopenshell.guid.new(),
        Name="Arched Window",
        Representation=window_shape,
        ObjectPlacement=window_placement
    )


    return model



def test_ifc_quality_validator_v2():


    print(
        "\n====== IFC QUALITY VALIDATOR V2 ======"
    )


    model = create_test_ifc()


    output_path = (
        "exports/"
        "test_quality_validator.ifc"
    )


    os.makedirs(
        "exports",
        exist_ok=True
    )


    model.write(
        output_path
    )



    validator = IFCQualityValidatorV2()


    result = validator.validate(
        output_path
    )


    print(
        "\n====== VALIDATION RESULT ======"
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
        result["checks"]["file_exists"]
    )


    assert (
        result["checks"]["reopen"]
    )


    assert (
        result["checks"]["IfcProject"]
    )


    assert (
        result["checks"]["IfcContext"]
    )


    assert (
        result["checks"]["IfcBuilding"]
    )


    assert (
        result["statistics"]["walls"]
        >=
        1
    )


    assert (
        result["statistics"]["columns"]
        >=
        1
    )


    assert (
        result["statistics"]["windows"]
        >=
        1
    )


    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_ifc_quality_validator_v2()