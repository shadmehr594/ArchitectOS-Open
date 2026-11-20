from core.architecture.reasoning.space_generation_reasoner import (
    SpaceGenerationReasoner
)

import pprint



print(
    "\n========== SPACE GENERATION REASONER TEST ==========\n"
)



reasoner = SpaceGenerationReasoner()



intent = {

    "building_type": "villa",

    "requirements": [

        "terrace",

        "balcony",

        "garden",

        "parking"

    ]

}



result = reasoner.generate(

    intent

)



print(
    "\n====== GENERATED SPACES ======\n"
)

pprint.pp(

    result.get(
        "generated_spaces"
    )

)



print(
    "\n====== RELATIONSHIPS ======\n"
)

pprint.pp(

    result.get(
        "relationships"
    )

)



print(
    "\n====== ORGANIZATION ======\n"
)

pprint.pp(

    result.get(
        "organization"
    )

)



print(
    "\n====================================================\n"
)