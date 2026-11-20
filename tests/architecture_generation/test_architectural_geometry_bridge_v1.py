import pprint


from core.architecture.geometry.architectural_geometry_bridge_v1 import (
    ArchitecturalGeometryBridgeV1
)



geometry_intent = {


    "spaces":[

        {
            "name":"living",
            "floor":"ground_floor"
        },

        {
            "name":"kitchen",
            "floor":"ground_floor"
        },

        {
            "name":"master_bedroom",
            "floor":"upper_floor"
        }

    ],


    "vertical_elements":[

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

}



result = ArchitecturalGeometryBridgeV1().generate(
    geometry_intent
)


print(
    "\n====== GEOMETRY BRIDGE OUTPUT ======\n"
)


pprint.pp(
    result
)