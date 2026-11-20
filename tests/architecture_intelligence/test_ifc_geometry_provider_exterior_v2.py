import ifcopenshell

from core.bim.geometry.ifc_geometry_provider import IFCGeometryProvider



def create_ifc_context():


    model = ifcopenshell.file(
        schema="IFC4"
    )


    owner_history = None


    context = model.create_entity(
        "IfcGeometricRepresentationContext",
        ContextIdentifier="Model",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5
    )


    return (
        model,
        owner_history,
        context
    )



def test_ifc_geometry_provider_exterior_v2():


    print(
        "\n====== IFC GEOMETRY PROVIDER EXTERIOR V2 ======"
    )


    model, owner_history, context = create_ifc_context()



    provider = IFCGeometryProvider(
        model,
        owner_history,
        context
    )



    wall = provider.create_wall_geometry(

        {

            "name": "Facade Stone Wall",

            "length": 20.0,

            "height": 3.2,

            "thickness": 0.35,

            "alignment": "external"

        }

    )



    column = provider.create_column_geometry(

        {

            "name": "Classical Column",

            "profile": "classical",

            "height": 3.2,

            "width": 0.5,

            "depth": 0.5

        }

    )



    window = provider.create_window_geometry(

        {

            "name": "Arched Window",

            "width": 1.5,

            "height": 2.2,

            "thickness": 0.2

        }

    )



    result = {


        "wall": wall,

        "column": column,

        "window": window


    }



    print(
        "\n====== REAL GEOMETRY RESULT ======"
    )


    print(result)



    assert (
        wall is not None
    )


    assert (
        column is not None
    )


    assert (
        window is not None
    )



    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_ifc_geometry_provider_exterior_v2()