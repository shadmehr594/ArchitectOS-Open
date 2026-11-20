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

from core.architecture.reasoning.architectural_layout_reasoner_v1 import (
    ArchitecturalLayoutReasonerV1
)



print(
    "\n========== ARCHITECTURAL LAYOUT REASONER TEST =========="
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



space_engine = SpaceGenerationReasoner()

spaces = space_engine.generate(
    intent
)



layout_engine = LayoutReasonerV2()

layout = layout_engine.generate(

    spaces.get(
        "generated_spaces"
    ),

    spaces.get(
        "relationships"
    ),

    {}

)



contract_engine = ArchitecturalSpatialContract()

contract = contract_engine.generate(

    layout,

    spaces

)



reasoner = ArchitecturalLayoutReasonerV1()


result = reasoner.generate(
    contract
)



print(
    "\n====== ARCHITECTURAL DESIGN OUTPUT ======"
)

pprint.pp(
    result
)

print(
    "\n=========================================="
)