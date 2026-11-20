class BoundaryWallReasoner:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🧱 BOUNDARY WALL REASONER v1.0 ONLINE"
        )


    def analyze(
        self,
        style,
        materials
    ):


        if style in [
            "roman_classic",
            "classic"
        ]:

            return {

                "boundary_wall": {

                    "type": "classical_stone_wall",

                    "elements": [

                        "travertine_base",
                        "stone_columns",
                        "decorative_panels",
                        "cornice"

                    ],

                    "gate_support": [

                        "stone_frame",
                        "classical_proportion"

                    ]

                },

                "source":
                "architectural_knowledge"

            }



        if style in [
            "iranian_traditional",
            "iranian_brick"
        ]:

            return {

                "boundary_wall": {

                    "type":
                    "traditional_iranian_wall",

                    "elements": [

                        "brick_pattern",
                        "stucco",
                        "tile_details",
                        "traditional_niches"

                    ],

                    "character":
                    "local_identity"

                },

                "source":
                "architectural_knowledge"

            }



        return {

            "boundary_wall": {

                "type":
                "modern_boundary_wall",

                "elements": [

                    "stone_surface",
                    "metal_panels",
                    "lighting"

                ]

            },

            "source":
            "architectural_knowledge"

        }