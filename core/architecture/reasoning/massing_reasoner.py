class MassingReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧱 MASSING REASONER v1.0 ONLINE"
        )



    def analyze(
        self,
        form_analysis,
        constraints,
        design_concept
    ):


        massing_options = []

        spatial_strategy = []



        forms = form_analysis.get(
            "form_options",
            []
        )



        logic = form_analysis.get(
            "form_logic",
            []
        )



        # ==================================
        # COMPACT MASS
        # ==================================

        if (
            "compact_mass" in forms
        ):


            massing_options.append(

                {

                    "type":
                    "compact_block",


                    "logic":
                    [

                        "create a unified building volume",

                        "protect sensitive spaces",

                        "reduce uncontrolled exposure"

                    ]

                }

            )



        # ==================================
        # COURTYARD
        # ==================================

        if (
            "courtyard_form" in forms
            or
            "central_courtyard" in forms
        ):


            massing_options.append(

                {

                    "type":
                    "courtyard_massing",


                    "logic":
                    [

                        "organize volumes around internal open space",

                        "improve daylight through central void",

                        "create private outdoor relationship"

                    ]

                }

            )


            spatial_strategy.append(
                "central open space can organize architectural experience"
            )



        # ==================================
        # L SHAPE
        # ==================================

        if (
            "l_shape" in forms
        ):


            massing_options.append(

                {

                    "type":
                    "l_shaped_massing",


                    "logic":
                    [

                        "create protected outdoor edge",

                        "connect main spaces with landscape",

                        "define semi-private courtyard"

                    ]

                }

            )


            spatial_strategy.append(
                "building wings can define outdoor zones"
            )



        # ==================================
        # GENERAL
        # ==================================

        if not massing_options:


            massing_options.append(

                {

                    "type":
                    "adaptive_massing",


                    "logic":
                    [

                        "massing should evolve from architectural concept"

                    ]

                }

            )



        return {


            "massing_options":
            massing_options,


            "spatial_strategy":
            spatial_strategy,


            "form_logic":
            logic,


            "source":
            "architectural_reasoning"

        }