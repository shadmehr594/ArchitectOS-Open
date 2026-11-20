from core.architecture.knowledge.building_program_knowledge import (
    BuildingProgramKnowledge
)
class SpaceGenerationReasoner:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🏗 SPACE GENERATION REASONER v1.0 ONLINE"
        )

        self.program_knowledge = BuildingProgramKnowledge()



    def generate(
        self,
        intent,
        site_analysis=None
    ):


        result = {


            "generated_spaces": [],

            "relationships": [],

            "organization": {}

        }



        building_type = intent.get(
            "building_type"
        )


        requirements = intent.get(
            "requirements",
            []
        )


        program = self.program_knowledge.get_program(
            building_type
        )



        # ==================================
        # BUILDING PROGRAM
        # ==================================

        spaces = []


        for item in program.get(
            "required_spaces",
            []
        ):

            spaces.append(
                item
            )


        for item in program.get(
            "optional_spaces",
            []
        ):

            if item["name"] in requirements:

                spaces.append(
                    item
                )


        result["generated_spaces"] = spaces


        result["relationships"].extend(

            program.get(
                "relationships",
                []
            )

        )


        # ==================================
        # ORGANIZATION FROM PROGRAM KNOWLEDGE
        # ==================================

        organization = {}


        for space in result["generated_spaces"]:


            zone = space.get(
                "zone",
                "unknown"
            )


            if zone not in organization:

                organization[zone] = []


            organization[zone].append(
                space["name"]
            )


        result["organization"] = organization

        return result