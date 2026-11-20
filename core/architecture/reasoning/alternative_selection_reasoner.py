class AlternativeSelectionReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🎯 ALTERNATIVE SELECTION REASONER v1.0 ONLINE"
        )



    def select(
        self,
        alternatives,
        intent,
        site_analysis
    ):


        selected = None

        reasons = []



        priorities = intent.get(
            "priorities",
            []
        )


        site = intent.get(
            "site",
            {}
        )


        neighbors = site.get(
            "neighbors",
            {}
        )



        # ==================================
        # PRIVACY PRIORITY
        # ==================================

        if (
            "privacy" in priorities
            or
            (
                neighbors.get("east")
                and
                neighbors.get("west")
            )
        ):


            for item in alternatives:


                if item.get(
                    "name"
                ) == "protected_compact_mass_strategy":


                    selected = item


                    reasons.append(
                        "privacy conditions support protected mass strategy"
                    )


                    break



        # ==================================
        # OUTDOOR RELATIONSHIP
        # ==================================

        if selected is None:


            if (
                "garden" in intent.get(
                    "requirements",
                    []
                )
                or
                "outdoor" in priorities
            ):


                for item in alternatives:


                    if item.get(
                        "name"
                    ) == "south_open_space_strategy":


                        selected = item


                        reasons.append(
                            "outdoor relationship is an important design goal"
                        )


                        break



        # ==================================
        # DAYLIGHT / EXPERIENCE
        # ==================================

        if selected is None:


            for item in alternatives:


                if item.get(
                    "name"
                ) == "central_courtyard_strategy":


                    selected = item


                    reasons.append(
                        "courtyard strategy supports daylight and spatial experience"
                    )


                    break



        return {


            "selected_alternative":
            selected,


            "reasons":
            reasons,


            "source":
            "architectural_reasoning"

        }