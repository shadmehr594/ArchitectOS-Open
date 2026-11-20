"""
ArchitectOS Vertical Circulation Intelligence v1.0

Architectural reasoning for:
- Stair
- Ramp
"""


class VerticalCirculationIntelligence:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🌀 Vertical Circulation Intelligence v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # CREATE STAIR DECISION
    # ==================================================

    def create_stair(
        self,
        stair_id,
        levels,
        role="vertical_connector",
        location_reason=None
    ):


        return {


            "id":

                stair_id,


            "type":

                "stair",


            "role":

                role,


            "connects":

                levels,


            "reasoning":

            {

                "location":

                    location_reason or []

            },


            "semantic":

            {

                "architectural":

                    True

            }

        }



    # ==================================================
    # CREATE RAMP DECISION
    # ==================================================

    def create_ramp(
        self,
        ramp_id,
        connects,
        slope=None,
        role="accessibility"
    ):


        return {


            "id":

                ramp_id,


            "type":

                "ramp",


            "role":

                role,


            "connects":

                connects,


            "slope":

                slope,


            "semantic":

            {

                "architectural":

                    True

            }

        }



    # ==================================================
    # VALIDATION
    # ==================================================

    def validate(
        self,
        element
    ):


        required = [

            "id",

            "type",

            "role",

            "connects"

        ]


        for key in required:


            if key not in element:

                return False



        return True