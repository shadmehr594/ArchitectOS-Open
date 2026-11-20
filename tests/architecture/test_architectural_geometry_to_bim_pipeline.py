"""
ArchitectOS Architectural Geometry To BIM Pipeline Test v1.0
"""


from core.architecture.geometry.architectural_geometry_pipeline_v1 import (
    ArchitecturalGeometryPipelineV1
)



def test_architectural_geometry_to_bim_pipeline():


    print(
        "\n"
        "==============================\n"
        "ARCHITECTURAL GEOMETRY TO BIM TEST\n"
        "==============================\n"
    )


    placement_output = {


        "floors":

        {

            "F1":

            {

                "height":
                    3.2,


                "spaces":

                [

                    {

                        "name":
                            "Main_Hall",


                        "zone":
                            "public",


                        "role":
                            "public_space",


                        "geometry_type":
                            "room"

                    },


                    {

                        "name":
                            "Office_01",


                        "zone":
                            "private",


                        "role":
                            "workspace",


                        "geometry_type":
                            "room"

                    }

                ]

            }

        },


        "vertical_core":

        [

            {

                "name":
                    "stairs",


                "placement_intent":
                    "central_core",


                "continuous":
                    True

            },


            {

                "name":
                    "elevator",


                "placement_intent":
                    "central_core",


                "continuous":
                    True

            }

        ]

    }



    pipeline = ArchitecturalGeometryPipelineV1()



    result = pipeline.generate(

        placement_output,

        facade_context={

            "style":
                "modern",

            "climate":
                "temperate"

        }

    )



    print(
        "\nGEOMETRY SPACES:"
    )

    for item in result["geometry"]["spaces"]:

        print(
            item
        )



    print(
        "\nBIM ELEMENTS:"
    )


    for item in result["architectural_bim"]["bim_elements"]:

        print(
            item
        )



    print(
        "\nENRICHED BIM:"
    )


    for item in result["enriched_bim"]["bim_elements"]:

        print(
            item
        )



    assert result["geometry"]


    assert result["architectural_bim"]


    assert result["enriched_bim"]



    assert (
        result["enriched_bim"]["element_count"]
        >= 0
    )



    print(

        "\n"
        "✅ ARCHITECTURAL GEOMETRY → BIM PIPELINE PASSED"

    )