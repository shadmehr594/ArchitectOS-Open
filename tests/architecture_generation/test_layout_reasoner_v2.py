import pprint


from core.architecture.reasoning.space_generation_reasoner import (
    SpaceGenerationReasoner
)


from core.architecture.reasoning.layout_reasoner_v2 import (
    LayoutReasonerV2
)



print(
    "\n========== LAYOUT REASONER V2 TEST ==========\n"
)



intent = {

    "building_type":
        "villa",

    "requirements":

        [

            "garden",

            "parking"

        ]

}



space_reasoner = SpaceGenerationReasoner()



space_result = space_reasoner.generate(
    intent
)



print(
    "\n====== SPACE OUTPUT ======"
)


pprint.pp(
    space_result
)



layout_reasoner = LayoutReasonerV2()



layout = layout_reasoner.generate(

    space_result["generated_spaces"],

    space_result["relationships"]

)



print(
    "\n====== LAYOUT OUTPUT ======"
)


pprint.pp(
    layout
)


print(
    "\n============================================"
)