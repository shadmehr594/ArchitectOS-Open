class RoofFormReasoner:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🏛 ROOF FORM REASONER v1.0 ONLINE"
        )


    def analyze(
        self,
        style,
        design_intent
    ):


        roof = {}


        if style == "roman_classic":


            roof = {

                "roof_type":
                "classical_dome",


                "elements":
                [
                    "central_dome",
                    "stone_drum",
                    "lantern",
                    "classical_cornice"
                ],


                "composition":
                "central_axis_focus",


                "skyline":
                "monumental"

            }



        elif style == "classic":


            roof = {

                "roof_type":
                "classical_roof",


                "elements":
                [
                    "cornice",
                    "symmetrical_roof_form"
                ],


                "skyline":
                "formal"

            }



        elif style == "iranian_islamic":


            roof = {

                "roof_type":
                "iranian_dome",


                "elements":
                [
                    "central_dome",
                    "turquoise_tile",
                    "brick_detail",
                    "muqarnas"
                ],


                "skyline":
                "traditional_identity"

            }



        elif style == "iranian_brick":


            roof = {

                "roof_type":
                "brick_roof_language",


                "elements":
                [
                    "brick_vault",
                    "traditional_brick_details"
                ],


                "skyline":
                "warm_traditional"

            }



        else:


            roof = {

                "roof_type":
                "flat_roof",


                "elements":
                [
                    "minimal_parapet"
                ],


                "skyline":
                "modern"

            }



        return {

            "roof_strategy":
            roof,


            "source":
            "architectural_reasoning"

        }