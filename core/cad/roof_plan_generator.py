class RoofPlanGenerator:


    def __init__(self):

        print(
            "🏠 Roof Plan Generator Engine v24.4 ACTIVE"
        )


    def generate(
        self,
        bim
    ):


        model = bim.get(
            "model",
            {}
        )


        elements = model.get(
            "elements",
            {}
        )


        roof = elements.get(
            "roof",
            {}
        )


        green_roof = roof.get(
            "green_roof",
            False
        )


        terrace = roof.get(
            "terrace",
            False
        )


        zones = []


        if green_roof:

            zones.append(
                {
                    "zone":
                    "green_roof",

                    "type":
                    "vegetation",

                    "water_retention":
                    True
                }
            )


        if terrace:

            zones.append(
                {
                    "zone":
                    "terrace",

                    "type":
                    "usable_space"
                }
            )


        zones.append(
            {
                "zone":
                "drainage",

                "type":
                "roof_water_management"
            }
        )


        return {


            "engine":
                "roof_plan_generator_v24.4",


            "status":
                "generated",


            "roof_plan":{


                "levels":
                    1,


                "zones":
                    zones,


                "elements":
                    elements.get(
                        "roof_elements",
                        []
                    )

            }

        }