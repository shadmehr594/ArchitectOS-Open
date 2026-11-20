from core.architecture.reasoning.space_generation_reasoner import (
    SpaceGenerationReasoner
)

from core.architecture.reasoning.layout_reasoner_v2 import (
    LayoutReasonerV2
)

from core.architecture.contract.architectural_spatial_contract import (
    ArchitecturalSpatialContract
)

from core.architecture.reasoning.vertical_circulation_reasoner_v1 import (
    VerticalCirculationReasoner
)


intent = {

    "building_type":"villa",

    "requirements":[
        "garden",
        "parking",
        "elevator"
    ]

}


space = SpaceGenerationReasoner().generate(intent)


layout = LayoutReasonerV2().generate(
    space["generated_spaces"],
    space["relationships"]
)


contract = ArchitecturalSpatialContract().generate(
    layout,
    space
)


vertical = VerticalCirculationReasoner().generate(
    layout,
    contract
)


print(vertical)