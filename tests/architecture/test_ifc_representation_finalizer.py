import ifcopenshell


from core.architecture.bim.ifc_real_solid_builder_v1 import (
    IFCRealSolidBuilderV1
)


from core.architecture.bim.ifc_representation_finalizer_v1 import (
    IFCRepresentationFinalizerV1
)



def test_ifc_representation_finalizer():


    model = ifcopenshell.file(
        schema="IFC4"
    )


    wall = model.create_entity(

        "IfcWall",

        GlobalId="wall001",

        Name="Main_Wall"

    )



    solid_builder = IFCRealSolidBuilderV1(

        model,

        context={

            "floor_height":3.6,

            "wall_thickness":0.30

        }

    )



    solid = solid_builder.build(

        wall,

        {

            "geometry_type":
                "extruded_wall"

        }

    )



    finalizer = IFCRepresentationFinalizerV1(
        model
    )



    result = finalizer.finalize(

        wall,

        solid

    )



    assert (
        result.Representation
        is not None
    )


    representation = (
        result.Representation.Representations[0]
    )


    assert (
        representation.Items[0].is_a(
            "IfcExtrudedAreaSolid"
        )
    )


    print(
        "\n✅ IFC REPRESENTATION FINALIZER PASSED"
    )