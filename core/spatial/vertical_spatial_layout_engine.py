"""
ArchitectOS Vertical Spatial Layout Engine v1.0

Places vertical circulation elements
inside architectural floor layout.
"""


class VerticalSpatialLayoutEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"📐 Vertical Spatial Layout Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # PLACE ELEMENT
    # ==================================================

    def place_element(
        self,
        space_type,
        index
    ):


        positions = {


            "escalator_zone":

                {

                    "location":
                        "atrium",

                    "polygon":
                        [
                            [5,5],
                            [11.4,5],
                            [11.4,6],
                            [5,6]
                        ],

                    "clearance":
                        2.0

                },



            "moving_ramp_zone":

                {

                    "location":
                        "main_public_path",

                    "polygon":
                        [
                            [5,8],
                            [21,8],
                            [21,9.8],
                            [5,9.8]
                        ],

                    "shopping_flow":
                        True

                },



            "elevator_core":

                {

                    "location":
                        "central_core",

                    "polygon":
                        [
                            [10,10],
                            [14,10],
                            [14,14],
                            [10,14]
                        ],

                    "shaft":
                        True

                },



            "stair_core":

                {

                    "location":
                        "escape_core",

                    "polygon":
                        [
                            [0,10],
                            [4,10],
                            [4,14],
                            [0,14]
                        ],

                    "fire_route":
                        True

                },



            "vehicle_ramp_zone":

                {

                    "location":
                        "parking_access",

                    "polygon":
                        [
                            [0,0],
                            [10,0],
                            [10,6],
                            [0,6]
                        ]

                },



            "car_lift_zone":

                {

                    "location":
                        "parking_core",

                    "polygon":
                        [
                            [12,0],
                            [16,0],
                            [16,6],
                            [12,6]
                        ]

                }

        }



        result = positions.get(

            space_type,

            {

                "location":
                    "undefined",

                "polygon":
                    []

            }

        )


        result["type"] = space_type


        return result



    # ==================================================
    # APPLY TO PROGRAM
    # ==================================================

    def generate(
        self,
        program
    ):


        layout = []



        for index, space in enumerate(

            program.get(
                "spaces",
                []
            )

        ):


            space_type = space.get(
                "type"
            )


            if space_type in [

                "escalator_zone",
                "moving_ramp_zone",
                "elevator_core",
                "stair_core",
                "vehicle_ramp_zone",
                "car_lift_zone"

            ]:


                element = self.place_element(

                    space_type,

                    index

                )


                layout.append(element)



        return {


            "level":

                program.get(
                    "level"
                ),


            "vertical_layout":

                layout

        }