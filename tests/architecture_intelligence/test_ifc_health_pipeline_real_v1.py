import os

import ifcopenshell


from core.bim.geometry.ifc_geometry_provider import (
    IFCGeometryProvider
)

from core.bim.ifc_health_pipeline import (
    IFCHealthPipelineV1
)



def create_local_placement(
    model,
    x=0.0,
    y=0.0,
    z=0.0,
    relative_to=None
):


    axis = model.create_entity(
        "IfcAxis2Placement3D",
        Location=model.create_entity(
            "IfcCartesianPoint",
            Coordinates=(
                x,
                y,
                z
            )
        )
    )


    return model.create_entity(
        "IfcLocalPlacement",
        PlacementRelTo=relative_to,
        RelativePlacement=axis
    )





def create_real_health_test_ifc():


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



    project = model.create_entity(
        "IfcProject",
        GlobalId=ifcopenshell.guid.new(),
        Name="ArchitectOS Real Health Test"
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



    storey_placement = create_local_placement(
        model
    )


    storey = model.create_entity(
        "IfcBuildingStorey",
        GlobalId=ifcopenshell.guid.new(),
        Name="F1",
        Elevation=0.0,
        ObjectPlacement=storey_placement
    )



    # ==============================================
    # GEOMETRY PROVIDER
    # ==============================================


    provider = IFCGeometryProvider(
        model,
        None,
        context
    )



    wall_shape = provider.create_wall_geometry(

        {

            "name":
                "Facade Stone Wall",

            "length":
                20.0,

            "height":
                3.2,

            "thickness":
                0.35

        }

    )



    column_shape = provider.create_column_geometry(

        {

            "name":
                "Classical Column",

            "height":
                3.2,

            "width":
                0.5,

            "depth":
                0.5

        }

    )



    window_shape = provider.create_window_geometry(

        {

            "name":
                "Arched Window",

            "width":
                1.5,

            "height":
                2.2,

            "thickness":
                0.2

        }

    )



    # ==============================================
    # ELEMENT PLACEMENTS
    # ==============================================


    wall_placement = create_local_placement(
        model,
        0.0,
        0.0,
        0.0,
        storey.ObjectPlacement
    )


    column_placement = create_local_placement(
        model,
        5.0,
        0.0,
        0.0,
        storey.ObjectPlacement
    )


    window_placement = create_local_placement(
        model,
        2.0,
        0.0,
        1.0,
        storey.ObjectPlacement
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





def test_ifc_health_pipeline_real_v1():


    print(
        "\n====== IFC HEALTH PIPELINE REAL V1 ======"
    )



    model = create_real_health_test_ifc()



    os.makedirs(
        "exports",
        exist_ok=True
    )



    path = (
        "exports/"
        "test_real_health_pipeline.ifc"
    )



    model.write(
        path
    )



    pipeline = IFCHealthPipelineV1()



    result = pipeline.run(
        path
    )



    print(
        "\n====== REAL HEALTH RESULT ======"
    )


    print(
        result
    )



    assert (
        result["quality"]["score"]
        ==
        100
    )


    assert (
        result["spatial"]["score"]
        ==
        100
    )


    assert (
        result["overall"]["score"]
        ==
        100
    )


    assert (
        result["overall"]["status"]
        ==
        "healthy"
    )



    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_ifc_health_pipeline_real_v1()