import pprint


from core.architecture.geometry.architectural_geometry_bridge_v2 import (
    ArchitecturalGeometryBridgeV2
)



arrangement = {


    "floors":{


        "ground_floor":{

            "spaces":[


                {
                    "name":"living",
                    "x":0,
                    "y":0,
                    "width":6,
                    "depth":5
                },


                {
                    "name":"kitchen",
                    "x":6,
                    "y":0,
                    "width":3,
                    "depth":4
                }

            ]

        }

    }

}



vertical = [


    {
        "name":"stairs"
    },


    {
        "name":"elevator"
    },


    {
        "name":"ramp"
    }

]



result = ArchitecturalGeometryBridgeV2().generate(
    arrangement,
    vertical
)



print(
    "\n====== GEOMETRY BRIDGE V2 OUTPUT ======\n"
)


pprint.pp(
    result
)