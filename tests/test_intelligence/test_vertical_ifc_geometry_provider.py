from core.bim.geometry.ifc_geometry_provider import (
    IFCGeometryProvider
)


import ifcopenshell



def test_vertical_ifc_geometry_provider():


    print(
        "\n🏗️ Vertical IFC Geometry Provider v1.0 ACTIVE"
    )


    model = ifcopenshell.file(
        schema="IFC4"
    )


    context = model.create_entity(

        "IfcGeometricRepresentationContext",

        ContextIdentifier="Body",

        ContextType="Model"

    )


    provider = IFCGeometryProvider(

        model,

        None,

        context

    )


    stair = provider.create_stair_geometry(

        {

            "geometry":

            [

                [0,0],

                [4,4]

            ]

        }

    )


    transport = provider.create_transport_geometry(

        {

            "geometry":

            [

                [5,5],

                [11,6]

            ]

        }

    )


    proxy = provider.create_proxy_geometry(

        {

            "geometry":

            [

                [10,10],

                [14,14]

            ]

        }

    )


    print("\n===== RESULT =====")

    print("STAIR:", stair)

    print("TRANSPORT:", transport)

    print("PROXY:", proxy)



    assert stair is not None

    assert transport is not None

    assert proxy is not None



    print(
        "\n✅ VERTICAL IFC GEOMETRY PROVIDER TEST PASSED"
    )



if __name__ == "__main__":

    test_vertical_ifc_geometry_provider()