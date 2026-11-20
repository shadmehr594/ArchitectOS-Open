class FacadeCompositionReasoner:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🏛 FACADE COMPOSITION REASONER v1.0 ONLINE"
        )


    def analyze(
        self,
        style,
        facade_assembly
    ):


        composition = {}


        if style == "roman_classic":


            composition = {

                "organization":
                "symmetrical",


                "axis":
                "central_entrance_axis",


                "levels":
                {

                    "ground_floor":
                    {
                        "character":
                        "strong_stone_base"
                    },


                    "upper_floor":
                    {
                        "character":
                        "classical_window_rhythm"
                    },


                    "top":
                    {
                        "character":
                        "decorative_cornice"
                    }

                },


                "windows":
                {

                    "pattern":
                    "regular_spacing",


                    "proportion":
                    "vertical_classical"

                },


                "entrance":
                {

                    "importance":
                    "main_visual_focus",


                    "elements":
                    [
                        "arch",
                        "columns",
                        "stone_frame"
                    ]

                }

            }


        elif style == "classic":


            composition = {

                "organization":
                    "balanced_symmetrical_composition",

                "axis":
                    "formal_entrance_axis",

                "levels":
                    {

                        "ground_floor":
                            {
                                "character":
                                    "strong_stone_base"
                            },

                        "upper_floor":
                            {
                                "character":
                                    "balanced_classical_openings"
                            },

                        "top":
                            {
                                "character":
                                    "refined_cornice_termination"
                            }

                    },

                "windows":
                    {

                        "pattern":
                            "symmetrical_regular_spacing",

                        "proportion":
                            "vertical_balanced"

                    },

                "entrance":
                    {

                        "importance":
                            "formal_visual_focus",

                        "elements":
                            [
                                "stone_frame",
                                "pilasters",
                                "entrance_canopy"
                            ]

                    },

                "composition_rules":
                    [
                        "symmetry",
                        "balanced_proportion",
                        "formal_axis",
                        "controlled_classical_detail"
                    ]

            }


        elif style == "iranian_brick":


            composition = {

                "organization":
                "textured_wall_composition",


                "axis":
                "courtyard_relationship",


                "levels":
                {

                    "ground_floor":
                    {
                        "character":
                        "heavy_masonry_base"
                    }

                },


                "windows":
                {

                    "pattern":
                    "controlled_openings"

                }

            }


        elif style == "iranian_traditional":


            composition = {

                "organization":
                    "introverted_layered_composition",

                "axis":
                    "courtyard_and_entrance_relationship",

                "levels":
                    {

                        "ground_floor":
                            {
                                "character":
                                    "solid_earthen_base"
                            },

                        "upper_floor":
                            {
                                "character":
                                    "recessed_shaded_openings"
                            },

                        "top":
                            {
                                "character":
                                    "traditional_parapet_termination"
                            }

                    },

                "windows":
                    {

                        "pattern":
                            "deep_recessed_controlled_openings",

                        "proportion":
                            "vertical_traditional"

                    },

                "entrance":
                    {

                        "importance":
                            "controlled_transition_focus",

                        "elements":
                            [
                                "recessed_entry",
                                "traditional_arch",
                                "brick_frame"
                            ]

                    },

                "composition_rules":
                    [
                        "human_scale",
                        "deep_shadow",
                        "layered_facade",
                        "controlled_openings",
                        "material_texture",
                        "climate_response"
                    ]

            }


        elif style == "modern":


            composition = {

                "organization":
                    "clean_asymmetrical_composition",


                "axis":
                    "functional_entrance_axis",


                "levels":
                    {

                        "ground_floor":
                            {
                                "character":
                                    "transparent_public_base"
                            },


                        "upper_floor":
                            {
                                "character":
                                    "controlled_private_openings"
                            },


                        "top":
                            {
                                "character":
                                    "minimal_flat_roof_termination"
                            }

                    },


                "windows":
                    {

                        "pattern":
                            "large_controlled_openings",


                        "proportion":
                            "horizontal_modern"

                    },


                "entrance":
                    {

                        "importance":
                            "clear_visual_focus",


                        "elements":
                            [
                                "minimal_canopy",
                                "glass_entry",
                                "metal_frame"
                            ]

                    },


                "composition_rules":
                    [
                        "simple_geometry",
                        "clean_lines",
                        "controlled_glazing",
                        "horizontal_emphasis"
                    ]

            }



        return {

            "facade_composition":
            composition,


            "source":
            "architectural_reasoning"

        }