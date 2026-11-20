class ArchitecturalDesignGenerator:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🏛 DESIGN GENERATOR v1.0 ONLINE"
        )



    def generate(
        self,
        intent,
        site_analysis,
        massing_analysis,
        decisions
    ):


        design_direction = []

        architectural_strategy = []

        spatial_character = []



        # ==================================
        # SITE RESPONSE
        # ==================================

        if site_analysis:


            design_direction.append(

                "design should respond to site conditions"

            )


            architectural_strategy.append(

                "building placement should consider orientation, access and privacy"

            )



        # ==================================
        # MASSING RESPONSE
        # ==================================

        massing_options = massing_analysis.get(
            "massing_options",
            []
        )


        selected_massing = None



        if massing_options:


            selected_massing = (
                massing_options[0]
                .get(
                    "type"
                )
            )



        # ==================================
        # SPACE RESPONSE
        # ==================================

        requirements = intent.get(
            "requirements",
            []
        )


        if "garden" in requirements:


            architectural_strategy.append(

                "main living spaces should maintain relationship with landscape"

            )



        if "pool" in requirements:


            architectural_strategy.append(

                "outdoor recreational spaces should connect with main social spaces"

            )



        # ==================================
        # CHARACTER
        # ==================================

        style = intent.get(
            "style"
        )


        if style:


            spatial_character.append(
                f"{style} architectural expression"
            )


        else:


            spatial_character.append(

                "adaptive architectural character"

            )



        # ==================================
        # FINAL DESIGN INTENT
        # ==================================

        return {


            "design_direction":
            design_direction,


            "architectural_strategy":
            architectural_strategy,


            "massing_direction":
            selected_massing,


            "spatial_character":
            spatial_character,


            "source":
            "architectural_reasoning"

        }