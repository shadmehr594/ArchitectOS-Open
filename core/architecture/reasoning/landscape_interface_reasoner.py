class LandscapeInterfaceReasoner:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🌿 LANDSCAPE INTERFACE REASONER v1.0 ONLINE"
        )


    def analyze(
        self,
        style,
        climate,
        spaces
    ):


        # ==========================
        # ROMAN / CLASSIC
        # ==========================

        if style in [
            "roman_classic",
            "classic",
            "neoclassical"
        ]:

            return {

                "landscape_strategy": {

                    "type":
                    "classical_formal_garden",

                    "elements": [

                        "central_axis",
                        "stone_paving",
                        "fountain",
                        "symmetrical_planting",
                        "formal_entrance_path"

                    ],

                    "outdoor_spaces": [

                        "terrace",
                        "pool",
                        "garden"

                    ]

                },

                "source":
                "architectural_knowledge"

            }



        # ==========================
        # IRANIAN TRADITIONAL
        # ==========================

        if style in [
            "iranian_traditional",
            "persian_classical"
        ]:

            return {

                "landscape_strategy": {

                    "type":
                    "iranian_courtyard_garden",

                    "elements": [

                        "central_water_feature",
                        "trees",
                        "brick_paving",
                        "garden_axis",
                        "shaded_seating"

                    ],

                    "outdoor_spaces": [

                        "courtyard",
                        "veranda",
                        "garden"

                    ]

                },

                "source":
                "architectural_knowledge"

            }



        # ==========================
        # MODERN
        # ==========================

        return {

            "landscape_strategy": {

                "type":
                "modern_minimal_landscape",

                "elements": [

                    "linear_planting",
                    "minimal_paving",
                    "water_reflection",
                    "outdoor_lounge"

                ],

                "outdoor_spaces": [

                    "terrace",
                    "garden"

                ]

            },

            "source":
            "architectural_knowledge"

        }