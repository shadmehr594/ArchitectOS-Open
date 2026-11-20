class MassingSelectionReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🎯 MASSING SELECTION REASONER v1.0 ONLINE"
        )



    def select(
        self,
        intent,
        site_analysis,
        massing_analysis
    ):


        options = massing_analysis.get(
            "massing_options",
            []
        )


        selected = None

        reasons = []



        requirements = intent.get(
            "requirements",
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
        # LANDSCAPE RELATIONSHIP
        # ==================================

        if (
            "garden" in requirements
            or
            "pool" in requirements
        ):


            for option in options:

                if option.get("type") == "l_shaped_massing":

                    selected = option

                    reasons.append(
                        "outdoor requirements support open edge massing"
                    )

                    break



        # ==================================
        # PRIVACY CONDITIONS
        # ==================================

        if selected is None:


            if (
                neighbors.get("east")
                or
                neighbors.get("west")
            ):


                for option in options:

                    if option.get("type") == "courtyard_massing":

                        selected = option

                        reasons.append(
                            "neighbor conditions support protected internal open space"
                        )

                        break



        # ==================================
        # DEFAULT
        # ==================================

        if selected is None:


            selected = (
                options[0]
                if options
                else None
            )


            reasons.append(
                "default architectural massing selection"
            )



        return {


            "selected_massing":
            selected.get("type")
            if selected
            else None,


            "reasoning":
            reasons,


            "source":
            "architectural_reasoning"

        }