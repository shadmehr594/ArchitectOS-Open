import pprint


from core.architecture.geometry.architectural_geometry_intent_generator_v1 import (
    ArchitecturalGeometryIntentGeneratorV1
)


placement = {

    "floors":{

        "ground_floor":{

            "spaces":[

                {
                    "name":"living",
                    "zone":"public",
                    "design_requirements":{
                        "daylight":"high"
                    }
                }

            ]

        }

    },


    "vertical_core":[

        {
            "name":"stairs",
            "placement_intent":"central_core"
        },

        {
            "name":"elevator",
            "placement_intent":"central_core"
        }

    ]

}



result = ArchitecturalGeometryIntentGeneratorV1().generate(
    placement
)


print(
    "\n====== ARCHITECTURAL GEOMETRY INTENT ======\n"
)


pprint.pp(
    result
)