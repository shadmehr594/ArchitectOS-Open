"""
ArchitectOS Opening Reasoner V1

Generates intelligent architectural openings:
doors and windows based on space function,
zone, privacy, daylight and facade relation.
"""


class OpeningReasonerV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🪟 OPENING REASONER V1 ONLINE"
        )



    def resolve(
        self,
        space
    ):


        name = space.get(
            "name",
            ""
        )


        zone = space.get(
            "zone"
        )


        role = space.get(
            "role"
        )


        position = space.get(
            "position_intent"
        )


        result = {

            "space":
                name,


            "openings":
                [],


            "design_logic":
                []

        }



        # ==================================
        # DOOR LOGIC
        # ==================================

        result["openings"].append(

            self.resolve_door(

                space

            )

        )



        # ==================================
        # WINDOW LOGIC
        # ==================================

        window = self.resolve_window(

            space

        )


        if window:

            result["openings"].append(

                window

            )



        result["design_logic"].extend(

            [

                "opening_size_based_on_space_function",

                "privacy_controls_window_ratio",

                "facade_connection_drives_opening_position"

            ]

        )


        return result





    # ==================================
    # DOOR RESOLVER
    # ==================================


    def resolve_door(
        self,
        space
    ):


        role = space.get(
            "role"
        )


        zone = space.get(
            "zone"
        )


        if role == "social_space":

            return {

                "type":
                    "door",


                "category":
                    "main_access",


                "width":
                    1200,


                "height":
                    2400,


                "material":
                    "glass_aluminum",


                "reason":
                    "public_space_access"

            }



        if zone == "service":

            return {

                "type":
                    "door",


                "category":
                    "service_door",


                "width":
                    900,


                "height":
                    2100,


                "material":
                    "wood_or_metal",


                "reason":
                    "service_access"

            }



        return {

            "type":
                "door",


            "category":
                "internal_door",


            "width":
                900,


            "height":
                2100,


            "material":
                "wood",


            "reason":
                "standard_room_access"

        }





    # ==================================
    # WINDOW RESOLVER
    # ==================================


    def resolve_window(
        self,
        space
    ):


        zone = space.get(
            "zone"
        )


        role = space.get(
            "role"
        )


        position = space.get(
            "position_intent"
        )



        # External spaces do not need normal windows

        if zone == "external":

            return None




        if role == "social_space":

            return {

                "type":
                    "window",


                "category":
                    "large_daylight_window",


                "width":
                    2400,


                "height":
                    1800,


                "sill_height":
                    600,


                "material":
                    "glass_aluminum",


                "opening_ratio":
                    0.45,


                "reason":
                    "daylight_and_visual_connection"

            }




        if zone == "private":

            return {

                "type":
                    "window",


                "category":
                    "privacy_window",


                "width":
                    1500,


                "height":
                    1500,


                "sill_height":
                    900,


                "material":
                    "glass_aluminum",


                "opening_ratio":
                    0.25,


                "reason":
                    "controlled_privacy_daylight"

            }




        if zone == "service":

            return {

                "type":
                    "window",


                "category":
                    "service_window",


                "width":
                    900,


                "height":
                    900,


                "sill_height":
                    1200,


                "material":
                    "glass",


                "opening_ratio":
                    0.15,


                "reason":
                    "ventilation"

            }



        return None