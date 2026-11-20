"""
ArchitectOS Door / Window Placement Engine v1.0

Creates openings based on architectural rules.
"""


class OpeningPlacementEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🚪 Window Door Placement Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # WINDOW RULE
    # ==================================================

    def create_window(
        self,
        room,
        edge_type
    ):


        room_type = room.get(
            "type"
        )



        if room_type == "living":


            return {

                "type":
                    "window",

                "room":
                    room_type,

                "edge":
                    edge_type,

                "source":
                    "facade"

            }



        if room_type in [

            "bedroom",

            "master_bedroom"

        ]:


            return {

                "type":
                    "window",

                "room":
                    room_type,

                "edge":
                    edge_type,

                "source":
                    "lightwell_or_facade",

                "rule":
                    "no_direct_opposite"

            }



        return None



    # ==================================================
    # DOOR RULE
    # ==================================================

    def create_door(
        self,
        room
    ):


        room_type = room.get(
            "type"
        )


        return {


            "type":
                "door",


            "room":
                room_type,


            "access":

            (

                "corridor"

                if room_type != "living"

                else

                "entrance"

            )

        }



    # ==================================================
    # GENERATE
    # ==================================================

    def generate(
        self,
        geometry
    ):


        openings = []



        for room in geometry.get(
            "rooms",
            []
        ):


            window = self.create_window(

                room,

                "external"

            )


            if window:


                openings.append(
                    window
                )
                

            if room.get(
                "type"
            ) in [

                "bathroom",

                "wc"

            ]:


                openings.append({

                    "type":
                        "vent",


                    "room":
                        room.get(
                            "type"
                        ),


                    "source":
                        "bathroom_duct"

                })



            door = self.create_door(

                room

            )


            openings.append(
                door
            )



        return {


            "openings":
                openings

        }