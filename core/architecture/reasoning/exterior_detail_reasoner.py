class ExteriorDetailReasoner:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🪟 EXTERIOR DETAIL REASONER v1.0 ONLINE"
        )


    def analyze(
        self,
        style,
        facade_language,
        materials
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

                "exterior_details": {

                    "windows": [

                        "stone_window_frames",
                        "arched_openings",
                        "decorative_window_trim"

                    ],

                    "vertical_elements": [

                        "columns",
                        "pilasters",
                        "classical_capitals"

                    ],

                    "horizontal_elements": [

                        "cornice",
                        "stone_bands"

                    ],

                    "ornaments": [

                        "balustrade",
                        "stone_panels",
                        "classical_moldings"

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

                "exterior_details": {

                    "windows": [

                        "orosi",
                        "wooden_frames",
                        "geometric_patterns"

                    ],

                    "wall_details": [

                        "brick_work",
                        "tile_work",
                        "muqarnas"

                    ],

                    "ornaments": [

                        "stucco_details",
                        "traditional_patterns",
                        "calligraphy"

                    ]

                },

                "source":
                "architectural_knowledge"

            }



        # ==========================
        # MODERN
        # ==========================

        return {

            "exterior_details": {

                "windows": [

                    "large_glazing",
                    "minimal_frames"

                ],

                "elements": [

                    "metal_details",
                    "wood_panels",
                    "shadow_gaps"

                ]

            },

            "source":
            "architectural_knowledge"

        }