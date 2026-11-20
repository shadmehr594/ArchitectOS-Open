"""
ArchitectOS Vertical Geometry Integration Engine v1.0

Converts vertical circulation layout
into BIM-ready geometry objects.
"""


class VerticalGeometryIntegrationEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🏗️ Vertical Geometry Integration Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # CREATE GEOMETRY
    # ==================================================

    def create_geometry(
        self,
        element
    ):


        element_type = element.get(
            "type"
        )



        polygon = element.get(
            "polygon",
            []
        )



        if element_type == "escalator_zone":


            return {


                "type":
                    "IfcTransportElement",


                "system":
                    "escalator",


                "geometry":
                    polygon,


                "placement":
                    element.get(
                        "location"
                    ),


                "clearance":
                    element.get(
                        "clearance"
                    )

            }



        if element_type == "moving_ramp_zone":


            return {


                "type":
                    "IfcTransportElement",


                "system":
                    "moving_ramp",


                "geometry":
                    polygon,


                "placement":
                    element.get(
                        "location"
                    ),


                "shopping_flow":
                    True

            }



        if element_type == "elevator_core":


            return {


                "type":
                    "IfcBuildingElementProxy",


                "system":
                    "elevator_core",


                "geometry":
                    polygon,


                "shaft":
                    True

            }



        if element_type == "stair_core":


            return {


                "type":
                    "IfcStair",


                "system":
                    "stair_core",


                "geometry":
                    polygon,


                "fire_route":
                    True

            }



        if element_type == "vehicle_ramp_zone":


            return {


                "type":
                    "IfcRamp",


                "system":
                    "vehicle_ramp",


                "geometry":
                    polygon

            }



        if element_type == "car_lift_zone":


            return {


                "type":
                    "IfcTransportElement",


                "system":
                    "car_lift",


                "geometry":
                    polygon

            }



        return None



    # ==================================================
    # GENERATE
    # ==================================================

    def generate(
        self,
        vertical_layout
    ):


        elements = []



        for item in vertical_layout.get(

            "vertical_layout",

            []

        ):


            geometry = self.create_geometry(

                item

            )


            if geometry:


                elements.append(

                    geometry

                )



        return {


            "level":
                vertical_layout.get(
                    "level"
                ),


            "elements":
                elements

        }