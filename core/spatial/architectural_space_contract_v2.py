"""
ArchitectOS Universal Architectural Space Contract v2.0

Common semantic contract for architectural entities:

- Room
- Courtyard
- Stair
- Ramp
- Corridor
- Entrance
- External Space
- Site
"""


class ArchitecturalSpaceContractV2:


    VERSION = "2.0"



    def __init__(self):

        print(
            f"🏛️ Architectural Space Contract v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # CREATE CONTRACT
    # ==================================================

    def create(
        self,
        space_id,
        space_type,
        requirements=None,
        adjacency=None,
        role=None
    ):


        return {


            "id":

                space_id,


            "type":

                space_type,


            "role":

                role,


            "requirements":

                requirements or {},


            "adjacency":

                adjacency or {},


            "semantic":

            {

                "architectural":

                    True

            }

        }



    # ==================================================
    # TYPE VALIDATION
    # ==================================================

    def validate(
        self,
        contract
    ):


        required = [

            "id",

            "type",

            "requirements",

            "adjacency"

        ]


        for key in required:


            if key not in contract:

                return False



        return True