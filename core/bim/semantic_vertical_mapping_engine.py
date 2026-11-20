"""
ArchitectOS Semantic BIM Vertical Mapping Engine v1.0

Maps vertical circulation geometry
into semantic BIM objects.
"""


class SemanticBIMVerticalMappingEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🧩 Semantic BIM Vertical Mapping Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # MAP ELEMENT
    # ==================================================

    def map_element(
        self,
        element
    ):


        system = element.get(
            "system"
        )



        if system == "escalator":

            return {

                "ifc_type":
                    "IfcTransportElement",

                "semantic_type":
                    "escalator",

                "function":
                    "public_vertical_flow",

                "requirements":
                    [
                        "safety_zone",
                        "landing",
                        "handrail"
                    ],

                "geometry":
                    element.get(
                        "geometry"
                    )

            }



        if system == "moving_ramp":

            return {

                "ifc_type":
                    "IfcTransportElement",

                "semantic_type":
                    "moving_ramp",

                "function":
                    "shopping_cart_flow",

                "requirements":
                    [
                        "landing",
                        "handrail",
                        "safety_zone"
                    ],

                "geometry":
                    element.get(
                        "geometry"
                    )

            }



        if system == "elevator_core":

            return {

                "ifc_type":
                    "IfcBuildingElementProxy",

                "semantic_type":
                    "elevator",

                "function":
                    "vertical_accessibility",

                "requirements":
                    [
                        "shaft",
                        "machine_room"
                    ],

                "geometry":
                    element.get(
                        "geometry"
                    )

            }



        if system == "stair_core":

            return {

                "ifc_type":
                    "IfcStair",

                "semantic_type":
                    "stair",

                "function":
                    "escape_route",

                "requirements":
                    [
                        "fire_access"
                    ],

                "geometry":
                    element.get(
                        "geometry"
                    )

            }



        return None



    # ==================================================
    # GENERATE
    # ==================================================

    def generate(
        self,
        geometry_result
    ):


        semantic_elements = []



        for element in geometry_result.get(

            "elements",

            []

        ):


            semantic = self.map_element(

                element

            )


            if semantic:

                semantic_elements.append(

                    semantic

                )



        return {


            "level":
                geometry_result.get(
                    "level"
                ),


            "semantic_elements":
                semantic_elements

        }