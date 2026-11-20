from core.architecture.knowledge.building_program_knowledge import (
    BuildingProgramKnowledge
)

import pprint


knowledge = BuildingProgramKnowledge()


result = knowledge.get_program(
    "villa"
)


print("\n====== VILLA PROGRAM ======\n")

pprint.pp(
    result
)

print(
    "\n=========================="
)