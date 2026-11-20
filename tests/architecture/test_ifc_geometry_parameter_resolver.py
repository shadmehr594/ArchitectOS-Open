"""
ArchitectOS IFC Geometry Parameter Resolver Test v1.0
"""


from core.architecture.bim.ifc_geometry_parameter_resolver_v1 import (
    IFCGeometryParameterResolverV1
)



def test_ifc_geometry_parameter_resolution():


    print(
        "\n"
        "================================\n"
        "IFC GEOMETRY PARAMETER RESOLUTION TEST\n"
        "================================\n"
    )



    resolved_geometry = {


        "geometry_elements":

        [

            {


                "ifc_class":
                    "IfcWall",


                "name":
                    "Main_Hall_Boundary",


                "level":
                    "F1",


                "geometry":

                {

                    "geometry_type":
                        "extruded_wall",


                    "height":
                        None,


                    "thickness":
                        None

                }

            },



            {

                "ifc_class":
                    "IfcSlab",


                "name":
                    "Main_Hall_Slab",


                "level":
                    "F1",


                "geometry":

                {

                    "geometry_type":
                        "floor",


                    "thickness":
                        None

                }

            },



            {

                "ifc_class":
                    "IfcSpace",


                "name":
                    "Main_Hall",


                "level":
                    "F1",


                "geometry":

                {

                    "geometry_type":
                        "space_volume",


                    "height":
                        None

                }

            }

        ]

    }



    resolver = IFCGeometryParameterResolverV1(

        context={

            "floor_height":
                3.2,


            "wall_thickness":
                0.25,


            "slab_thickness":
                0.20,


            "level_elevations":
            {

                "F1":
                    0.0

            },


            "wall_profile":
                "rectangular",


            "default_direction":
                [0,0,1]

        }

    )



    result = resolver.resolve(
        resolved_geometry["geometry_elements"]
    )



    print(
        "\nPARAMETERS:"
    )


    for element in result["geometry_parameters"]:

        print(element)



    wall = next(

        e for e in result["geometry_parameters"]

        if e["ifc_class"] == "IfcWall"

    )



    slab = next(

        e for e in result["geometry_parameters"]

        if e["ifc_class"] == "IfcSlab"

    )



    space = next(

        e for e in result["geometry_parameters"]

        if e["ifc_class"] == "IfcSpace"

    )



    assert (
        wall["geometry"]["height"]
        ==
        3.2
    )


    assert (
        wall["geometry"]["thickness"]
        ==
        0.25
    )



    assert (
        slab["geometry"]["thickness"]
        ==
        0.20
    )



    assert (
        space["geometry"]["height"]
        ==
        3.2
    )



    assert (
        result["element_count"]
        ==
        3
    )


    print(
        "\n✅ IFC GEOMETRY PARAMETER RESOLUTION PASSED"
    )