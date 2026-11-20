import ifcopenshell

from core.bim.geometry.ifc_geometry_provider import IFCGeometryProvider



def create_ifc_context():

    model = ifcopenshell.file(
        schema="IFC4"
    )

    owner_history = None

    return (
        model,
        owner_history
    )



def test_ifc_geometry_provider_exterior_v1():


    print(
        "\n====== IFC GEOMETRY PROVIDER EXTERIOR V1 ======"
    )


    model, owner_history = create_ifc_context()


    provider = IFCGeometryProvider(
        model,
        owner_history
    )



    wall_geometry = provider.create_wall_geometry(

        {

            "name": "Facade Stone Wall",

            "length": 20.0,

            "height": 3.2,

            "thickness": 0.35,

            "alignment": "external"

        }

    )



    column_geometry = provider.create_column_geometry(

        {

            "name": "Classical Column",

            "profile": "classical",

            "height": 3.2,

            "width": 0.5,

            "depth": 0.5

        }

    )



    window_geometry = provider.create_window_geometry(

        {

            "name": "Arched Opening",

            "width": 1.5,

            "height": 2.2,

            "thickness": 0.2

        }

    )



    result = {


        "geometry_elements": [


            {

                "ifc_class": "IfcWall",

                "name": "Facade Stone Wall",

                "geometry": wall_geometry

            },


            {

                "ifc_class": "IfcColumn",

                "name": "Classical Column",

                "geometry": column_geometry

            },


            {

                "ifc_class": "IfcWindow",

                "name": "Arched Opening",

                "geometry": window_geometry

            }


        ],


        "element_count": 3,


        "source": "ifc_geometry_provider"

    }



    print(
        "\n====== GEOMETRY PROVIDER RESULT ======"
    )


    print(
        result
    )



    assert (
        result["element_count"]
        ==
        3
    )


    assert (
        result["geometry_elements"][0]["ifc_class"]
        ==
        "IfcWall"
    )


    assert (
        result["geometry_elements"][1]["ifc_class"]
        ==
        "IfcColumn"
    )


    assert (
        result["geometry_elements"][2]["ifc_class"]
        ==
        "IfcWindow"
    )



    print(
        "\n====== TEST PASSED ======"
    )



if __name__ == "__main__":

    test_ifc_geometry_provider_exterior_v1()