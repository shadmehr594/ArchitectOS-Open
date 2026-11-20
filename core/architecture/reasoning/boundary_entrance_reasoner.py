class BoundaryEntranceReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🚪 BOUNDARY ENTRANCE REASONER v1.0 ONLINE"
        )



    def analyze(
        self,
        style,
        facade_language,
        materials
    ):


        result = {

            "boundary_system": {},

            "vehicle_entrance": {},

            "pedestrian_entrance": {},

            "source": "architectural_reasoning"

        }



        if style in [
            "roman_classic",
            "classic"
        ]:


            result["boundary_system"] = {

                "type": "classical_stone_boundary",

                "elements": [

                    "stone_plinth",

                    "stone_wall",

                    "decorative_cap",

                    "classical_balustrade"

                ]

            }



            result["vehicle_entrance"] = {

                "type": "monumental_gate",

                "elements": [

                    "stone_columns",

                    "arched_gate",

                    "stone_frame",

                    "lighting"

                ]

            }



            result["pedestrian_entrance"] = {

                "type": "classical_entry",

                "elements": [

                    "arched_door",

                    "stone_surround",

                    "entrance_canopy"

                ]

            }



        elif style == "iranian_brick":


            result["boundary_system"] = {

                "type": "traditional_brick_boundary",

                "elements": [

                    "brick_wall",

                    "brick_pattern",

                    "stone_base"

                ]

            }



            result["vehicle_entrance"] = {

                "type": "brick_arch_gate",

                "elements": [

                    "brick_arch",

                    "wooden_gate",

                    "traditional_details"

                ]

            }



            result["pedestrian_entrance"] = {

                "type": "traditional_entry",

                "elements": [

                    "brick_frame",

                    "wooden_door",

                    "decorative_details"

                ]

            }



        else:


            result["boundary_system"] = {

                "type": "modern_boundary",

                "elements": [

                    "stone_base",

                    "metal_panels",

                    "landscape_buffer"

                ]

            }



            result["vehicle_entrance"] = {

                "type": "modern_gate",

                "elements": [

                    "metal_gate",

                    "linear_lighting"

                ]

            }



            result["pedestrian_entrance"] = {

                "type": "modern_entry",

                "elements": [

                    "glass_door",

                    "metal_frame"

                ]

            }



        return result