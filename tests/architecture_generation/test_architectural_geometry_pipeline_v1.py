import pprint


from core.architecture.geometry.architectural_geometry_pipeline_v1 import (
    ArchitecturalGeometryPipelineV1
)



bridge_output = {


    "floorplans":{


        "ground_floor":{


            "rooms":[


                {

                    "name":"living",

                    "geometry":{

                        "x":0,

                        "y":0,

                        "width":6,

                        "depth":5

                    }

                },


                {

                    "name":"kitchen",

                    "geometry":{

                        "x":6,

                        "y":0,

                        "width":3,

                        "depth":4

                    }

                }

            ]

        }

    },


    "vertical_layout":{


        "level":"all",


        "vertical_layout":[


            {

                "name":"stairs",

                "type":"stair_core",

                "polygon":[]

            },


            {

                "name":"elevator",

                "type":"elevator_core",

                "polygon":[]

            }

        ]

    }

}



result = ArchitecturalGeometryPipelineV1().generate(
    bridge_output
)



print(
    "\n====== ARCHITECTURAL GEOMETRY PIPELINE OUTPUT ======\n"
)


pprint.pp(
    result
)