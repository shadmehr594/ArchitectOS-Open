class VerticalCirculationReasoner:

    VERSION = "1.0"


    def __init__(self):

        print(
            "🛗 VERTICAL CIRCULATION REASONER v1.0 ONLINE"
        )


    def generate(
        self,
        architectural_layout,
        contract
    ):

        result = {

            "vertical_elements": [],

            "connections": [],

            "rules": []

        }


        vertical_org = contract.get(
            "vertical_organization",
            {}
        )


        floors = list(
            vertical_org.keys()
        )


        # ==============================
        # STAIRS
        # ==============================

        if len(floors) > 1:

            result["vertical_elements"].append(

                {
                    "name": "stairs",

                    "type":
                        "stair",

                    "from":
                        floors[0],

                    "to":
                        floors[1],

                    "priority":
                        "high"

                }

            )


        # ==============================
        # ELEVATOR
        # ==============================

        result["vertical_elements"].append(

            {
                "name":
                    "elevator",

                "type":
                    "vertical_transport",

                "from":
                    floors[0] if floors else None,

                "to":
                    floors[-1] if floors else None,

                "priority":
                    "medium"

            }

        )


        # ==============================
        # RAMP
        # ==============================

        result["vertical_elements"].append(

            {

                "name":
                    "ramp",

                "type":
                    "accessibility",

                "connects":
                    "external_to_ground",

                "priority":
                    "medium"

            }

        )


        # ==============================
        # FUTURE SYSTEMS
        # ==============================

        result["rules"] = [

            "vertical_elements_connect_levels",

            "accessibility_requires_ramp",

            "multi_floor_buildings_require_vertical_core"

        ]


        return result