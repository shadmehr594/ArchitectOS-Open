import pprint


from core.architecture.reasoning.spatial_arrangement_reasoner_v1 import (
    SpatialArrangementReasonerV1
)



layout = {

    "spaces":[

        {
            "name":"living",
            "zone":"public"
        },

        {
            "name":"kitchen",
            "zone":"service"
        },

        {
            "name":"master_bedroom",
            "zone":"private"
        }

    ]

}



result = SpatialArrangementReasonerV1().generate(
    layout
)


print(
    "\n====== SPATIAL ARRANGEMENT OUTPUT ======\n"
)


pprint.pp(
    result
)