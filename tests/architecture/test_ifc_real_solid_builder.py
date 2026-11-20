import ifcopenshell


from core.architecture.bim.ifc_real_solid_builder_v1 import (
    IFCRealSolidBuilderV1
)



def test_ifc_real_solid_builder():


    model = ifcopenshell.file(
        schema="IFC4"
    )


    wall = model.create_entity(
        "IfcWall",
        GlobalId="wall001",
        Name="Main_Wall"
    )


    builder = IFCRealSolidBuilderV1(

        model,

        context={

            "floor_height":3.6,

            "wall_thickness":0.30

        }

    )



    solid = builder.build(

        wall,

        {

            "geometry_type":
                "extruded_wall"

        }

    )



    assert (
        solid.is_a(
            "IfcExtrudedAreaSolid"
        )
    )


    assert (
        solid.Depth
        ==
        3.6
    )


    print(
        "\n✅ IFC REAL SOLID BUILDER PASSED"
    )