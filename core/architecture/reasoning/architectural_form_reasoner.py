class ArchitecturalFormReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🏛 FORM REASONER v1.0 ONLINE"
        )



    def analyze(
        self,
        intent,
        constraints,
        selected_alternative
    ):


        form_options = []

        form_logic = []



        selected = selected_alternative.get(
            "selected_alternative",
            {}
        )


        strategy = selected.get(
            "name",
            ""
        )



        site = intent.get(
            "site",
            {}
        )


        neighbors = site.get(
            "neighbors",
            {}
        )


        requirements = intent.get(
            "requirements",
            []
        )



        # ==================================
        # PRIVACY BASED FORM
        # ==================================

        if (
            strategy ==
            "protected_compact_mass_strategy"
        ):


            form_options.extend(

                [
                    "compact_mass",
                    "courtyard_form"
                ]

            )


            form_logic.append(
                "form should reduce uncontrolled neighbor exposure"
            )



        # ==================================
        # OUTDOOR RELATIONSHIP
        # ==================================

        if (
            "garden" in requirements
            or
            "pool" in requirements
        ):


            form_options.append(
                "l_shape"
            )


            form_logic.append(
                "form should create meaningful outdoor relationship"
            )



        # ==================================
        # CENTRAL LIGHT
        # ==================================

        if (
            neighbors.get("east")
            and
            neighbors.get("west")
        ):


            form_options.append(
                "central_courtyard"
            )


            form_logic.append(
                "central void can improve daylight and privacy"
            )



        # ==================================
        # GENERAL FREEDOM
        # ==================================

        if not form_options:


            form_options.extend(

                [
                    "linear_form",
                    "compact_mass"
                ]

            )


            form_logic.append(
                "form should adapt to architectural concept"
            )



        return {


            "form_options":
            list(
                dict.fromkeys(
                    form_options
                )
            ),


            "form_logic":
            form_logic,


            "source":
            "architectural_reasoning"

        }