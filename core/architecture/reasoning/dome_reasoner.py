class DomeReasoner:


    VERSION = "1.1"



    def __init__(self):

        print(
            "🔵 DOME REASONER v1.1 ONLINE"
        )



    def analyze(
        self,
        style,
        roof_strategy,
        facade_composition
    ):


        result = {

            "dome_type": None,

            "elements": [],

            "character": None,

            "skyline_role": None,

            "status": "not_required",

            "reason": None,

            "source": "architectural_reasoning"

        }


        # ==================================================
        # NORMALIZE ROOF STRATEGY
        # ==================================================

        if not isinstance(
            roof_strategy,
            dict
        ):

            roof_strategy = {}


        roof_data = roof_strategy.get(
            "roof_strategy",
            roof_strategy
        )


        if not isinstance(
            roof_data,
            dict
        ):

            roof_data = {}


        roof_type = roof_data.get(
            "roof_type"
        )


        roof_elements = roof_data.get(
            "elements",
            []
        )


        if not isinstance(
            roof_elements,
            list
        ):

            roof_elements = []


        roof_text = " ".join(
            [
                str(roof_type or ""),
                *[
                    str(element)
                    for element in roof_elements
                ]
            ]
        ).lower()


        # ==================================================
        # EXPLICIT DOME REQUEST FROM ROOF CONTRACT
        # ==================================================

        explicit_dome_request = (
            "dome"
            in roof_text
        )


        # ==================================================
        # FLAT ROOF GUARD
        #
        # A flat roof must not receive a decorative dome
        # unless the roof contract explicitly requests one.
        # ==================================================

        if (
            roof_type == "flat_roof"
            and
            not explicit_dome_request
        ):

            result["status"] = "not_required"

            result["reason"] = (
                "flat_roof_without_explicit_dome_intent"
            )

            return result


        # ==================================================
        # ROMAN CLASSIC
        # ==================================================

        if style == "roman_classic":

            result["dome_type"] = (
                "roman_classical_dome"
            )

            result["elements"] = [

                "stone_dome",

                "classical_drum",

                "lantern",

                "cornice"

            ]

            result["character"] = (
                "monumental_classical"
            )

            result["skyline_role"] = (
                "central_visual_focus"
            )

            result["status"] = "resolved"



        # ==================================================
        # IRANIAN / ISLAMIC
        # ==================================================

        elif style in [

            "iranian_traditional",

            "iranian_islamic",

            "islamic_architecture"

        ]:

            result["dome_type"] = (
                "persian_islamic_dome"
            )

            result["elements"] = [

                "double_shell_dome",

                "brick_dome",

                "tile_decoration",

                "muqarnas_details"

            ]

            result["character"] = (
                "cultural_identity"
            )

            result["skyline_role"] = (
                "spiritual_landmark"
            )

            result["status"] = "resolved"



        # ==================================================
        # IRANIAN BRICK
        # ==================================================

        elif style == "iranian_brick":

            result["dome_type"] = (
                "brick_dome"
            )

            result["elements"] = [

                "brick_shell",

                "geometric_pattern",

                "traditional_detail"

            ]

            result["character"] = (
                "traditional_earth_expression"
            )

            result["skyline_role"] = (
                "architectural_identity"
            )

            result["status"] = "resolved"



        # ==================================================
        # CLASSIC
        # ==================================================

        elif style == "classic":

            result["dome_type"] = (
                "classical_dome"
            )

            result["elements"] = [

                "stone_dome",

                "drum",

                "decorative_cap"

            ]

            result["character"] = (
                "formal_classical"
            )

            result["skyline_role"] = (
                "main_axis_emphasis"
            )

            result["status"] = "resolved"



        # ==================================================
        # OTHER STYLES
        #
        # No invented dome.
        # Dome generation must come from explicit
        # architectural / roof intent.
        # ==================================================

        else:

            result["status"] = "not_required"

            result["reason"] = (
                "style_does_not_require_dome"
            )


        return result