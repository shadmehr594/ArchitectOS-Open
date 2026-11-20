import pprint


from core.architecture.reasoning.space_generation_reasoner import (
    SpaceGenerationReasoner
)


from core.architecture.reasoning.layout_reasoner_v2 import (
    LayoutReasonerV2
)


from core.architecture.contract.architectural_spatial_contract import (
    ArchitecturalSpatialContract
)



print(
    "\n========== SPATIAL CONTRACT TEST =========="
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


spaces = space_reasoner.generate(
    intent
)



layout_reasoner = LayoutReasonerV2()


layout = layout_reasoner.generate(

    spaces.get(
        "generated_spaces",
        []
    ),

    spaces.get(
        "relationships",
        []
    ),

    {}

)



contract_engine = ArchitecturalSpatialContract()



contract = contract_engine.generate(
    layout,
    spaces
)



print(
    "\n====== SPATIAL CONTRACT OUTPUT ======"
)


pprint.pp(
    contract
)


print(
    "\n======================================"
)