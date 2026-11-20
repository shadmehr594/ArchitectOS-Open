import os

import ifcopenshell


from core.bim.geometry.ifc_geometry_provider import (
    IFCGeometryProvider
)

from core.bim.ifc_health_pipeline import (
    IFCHealthPipelineV1
)



def create_pipeline_v1_1_ifc():


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


    project = model.create_entity(
        "IfcProject",
        GlobalId=ifcopenshell.guid.new(),
        Name="ArchitectOS Health Pipeline V1.1"
    )


    site = model.create_entity(
        "IfcSite",
        GlobalId=ifcopenshell.guid.new(),
        Name="Site"
    )


    building = model.create_entity(
        "IfcBuilding",
        GlobalId=ifcopenshell.guid.new(),
        Name="Building"
    )


    storey = model.create_entity(
        "IfcBuildingStorey",
        GlobalId=ifcopenshell.guid.new(),
        Name="F1",
        Elevation=0.0
    )


    storey.ObjectPlacement = model.create_entity(
        "IfcLocalPlacement",
        RelativePlacement=model.create_entity(
            "IfcAxis2Placement3D",
            Location=model.create_entity(
                "IfcCartesianPoint",
                Coordinates=(0.0,0.0,0.0)
            )
        )
    )


    provider = IFCGeometryProvider(
        model,
        None,
        context
    )


    wall_shape = provider.create_wall_geometry(
        {
            "name":
                "Exterior Wall",

            "length":
                25.0,

            "height":
                3.2,

            "thickness":
                0.35
        }
    )


    column_shape = provider.create_column_geometry(
        {
            "name":
                "Structural Column",

            "height":
                3.2,

            "width":
                0.5,

            "depth":
                0.5
        }
    )


    wall = model.create_entity(
        "IfcWall",
        GlobalId=ifcopenshell.guid.new(),
        Name="Exterior Wall",
        Representation=wall_shape,
        ObjectPlacement=model.create_entity(
            "IfcLocalPlacement",
            PlacementRelTo=storey.ObjectPlacement,
            RelativePlacement=model.create_entity(
                "IfcAxis2Placement3D",
                Location=model.create_entity(
                    "IfcCartesianPoint",
                    Coordinates=(0.0,0.0,0.0)
                )
            )
        )
    )


    column = model.create_entity(
        "IfcColumn",
        GlobalId=ifcopenshell.guid.new(),
        Name="Structural Column",
        Representation=column_shape,
        ObjectPlacement=model.create_entity(
            "IfcLocalPlacement",
            PlacementRelTo=storey.ObjectPlacement,
            RelativePlacement=model.create_entity(
                "IfcAxis2Placement3D",
                Location=model.create_entity(
                    "IfcCartesianPoint",
                    Coordinates=(5.0,0.0,0.0)
                )
            )
        )
    )


    model.create_entity(
        "IfcRelAggregates",
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=project,
        RelatedObjects=[site]
    )


    model.create_entity(
        "IfcRelAggregates",
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=site,
        RelatedObjects=[building]
    )


    model.create_entity(
        "IfcRelAggregates",
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=building,
        RelatedObjects=[storey]
    )


    model.create_entity(
        "IfcRelContainedInSpatialStructure",
        GlobalId=ifcopenshell.guid.new(),
        RelatingStructure=storey,
        RelatedElements=[
            wall,
            column
        ]
    )


    return model





def test_ifc_health_pipeline_v1_1():


    print(
        "\n====== IFC HEALTH PIPELINE V1.1 ======"
    )


    model = create_pipeline_v1_1_ifc()


    os.makedirs(
        "exports",
        exist_ok=True
    )


    path = (
        "exports/"
        "test_ifc_health_pipeline_v1_1.ifc"
    )


    model.write(
        path
    )


    pipeline = IFCHealthPipelineV1()


    result = pipeline.run(
        path
    )


    print(
        "\n====== HEALTH PIPELINE V1.1 RESULT ======"
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

    test_ifc_health_pipeline_v1_1()