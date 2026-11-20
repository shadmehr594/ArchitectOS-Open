class DesignAlternativeReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🔀 DESIGN ALTERNATIVE REASONER v1.0 ONLINE"
        )



    def generate(
        self,
        site_analysis,
        decision_model,
        intent
    ):


        alternatives = []



        site = intent.get(
            "site",
            {}
        )


        requirements = intent.get(
            "requirements",
            []
        )


        climate = site.get(
            "climate",
            {}
        )


        neighbors = site.get(
            "neighbors",
            {}
        )


        # ==================================
        # SOUTH OPEN SPACE STRATEGY
        # ==================================

        if site.get(
            "access",
            {}
        ).get(
            "main_access"
        ) == "south":


            alternatives.append(

                {

                    "name":
                    "south_open_space_strategy",


                    "concept":
                    [
                        "place main living relationship toward outdoor space",
                        "use southern access as design opportunity"
                    ],


                    "site_response":
                    [
                        "respond to south entrance",
                        "preserve meaningful outdoor relationship"
                    ]

                }

            )



        # ==================================
        # COURTYARD STRATEGY
        # ==================================

        alternatives.append(

            {

                "name":
                "central_courtyard_strategy",


                "concept":
                [
                    "create internal outdoor focus",
                    "improve daylight and privacy"
                ],


                "site_response":
                [
                    "suitable for privacy constraints",
                    "supports controlled natural light"
                ]

            }

        )



        # ==================================
        # COMPACT MASS STRATEGY
        # ==================================

        if neighbors.get(
            "east"
        ) and neighbors.get(
            "west"
        ):


            alternatives.append(

                {

                    "name":
                    "protected_compact_mass_strategy",


                    "concept":
                    [
                        "reduce uncontrolled neighbor exposure",
                        "prioritize privacy"
                    ],


                    "site_response":
                    [
                        "respond to adjacent boundaries"
                    ]

                }

            )



        return {

            "alternatives":
            alternatives,


            "source":
            "architectural_reasoning"

        }