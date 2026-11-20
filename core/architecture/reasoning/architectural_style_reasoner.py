class ArchitecturalStyleReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🎨 ARCHITECTURAL STYLE REASONER v1.0 ONLINE"
        )



    def analyze(
        self,
        intent,
        design_direction
    ):


        style = intent.get(
            "style",
            ""
        )


        candidates = []



        if style:

            candidates.append(
                style
            )


        else:


            if "modern" in str(
                design_direction
            ):

                candidates.append(
                    "modern"
                )


            else:

                candidates.extend(
                    [
                        "modern",
                        "classic",
                        "iranian_brick"
                    ]
                )



        return {


            "style_candidates":
            candidates,


            "design_direction":
            design_direction,


            "source":
            "architectural_reasoning"

        }