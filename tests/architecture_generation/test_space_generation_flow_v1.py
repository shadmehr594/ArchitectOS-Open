from core.architecture.knowledge.building_program_knowledge import (
    BuildingProgramKnowledge
)

from core.architecture.reasoning.space_generation_reasoner import (
    SpaceGenerationReasoner
)

import pprint


print(
    "\n========== ARCHITECTURAL PROGRAM FLOW TEST ==========\n"
)


print(
    "====== BUILDING PROGRAM KNOWLEDGE ======"
)

knowledge = BuildingProgramKnowledge()


program = knowledge.get_program(
    "villa"
)

pprint.pp(
    program
)


print(
    "\n====== SPACE GENERATION ======"
)

reasoner = SpaceGenerationReasoner()


result = reasoner.generate(

    {
        "building_type": "villa",

        "requirements":
        [
            "terrace",
            "balcony",
            "garden",
            "parking"
        ]
    }

)


pprint.pp(

    result

)


print(
    "\n===================================================="
)