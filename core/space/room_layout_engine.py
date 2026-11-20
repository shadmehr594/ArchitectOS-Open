"""
ArchitectOS Room Layout Engine v1.0

Places rooms according to architectural rules.
"""


class RoomLayoutEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🛋️ Room Layout Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # RESIDENTIAL
    # ==================================================

    def residential_layout(
        self,
        room_program,
        unit
    ):


        rooms = []



        for room in room_program.get(
            "rooms",
            []
        ):


            room_type = room.get(
                "type"
            )



            # ------------------------------
            # PUBLIC ZONE
            # ------------------------------

            if room_type in [

                "living",

                "dining"

            ]:


                rooms.append({

                    "type":
                        room_type,

                    "zone":
                        "public",

                    "location":
                        "facade"

                })



            # ------------------------------
            # BEDROOM
            # ------------------------------

            elif room_type in [

                "master_bedroom",

                "bedroom"

            ]:


                rooms.append({

                    "type":
                        room_type,

                    "zone":
                        "private",

                    "location":
                        "lightwell_or_facade",

                    "window_rule":
                        "no_direct_opposite"

                })



            # ------------------------------
            # KITCHEN
            # ------------------------------

            elif room_type == "kitchen_clean":


                rooms.append({

                    "type":
                        room_type,

                    "zone":
                        "service",

                    "location":
                        "near_living"

                })



            elif room_type == "kitchen_dirty":


                rooms.append({

                    "type":
                        room_type,

                    "zone":
                        "service",

                    "ventilation":
                        "separate_duct"

                })



            # ------------------------------
            # BATHROOM
            # ------------------------------

            elif room_type in [

                "bathroom",

                "wc",

                "master_bathroom"

            ]:


                rooms.append({

                    "type":
                        room_type,

                    "zone":
                        "service",

                    "ventilation":
                        "bathroom_duct"

                })



            else:


                rooms.append({

                    "type":
                        room_type

                })



        return {


            "unit":
                unit.get(
                    "id"
                ),


            "rooms":
                rooms,


            "rules":{


                "window_facing":
                    False,


                "separate_service_duct":
                    True

            }

        }



    # ==================================================
    # MAIN
    # ==================================================

    def generate(
        self,
        room_program,
        unit
    ):


        program_type = room_program.get(
            "type"
        )


        if program_type == "roof":


            return self.roof_layout(

                room_program,

                unit

            )



        if program_type in [

            "residential",

            "penthouse"

        ]:


            return self.residential_layout(

                room_program,

                unit

            )



        return {


            "unit":
                unit.get(
                    "id"
                ),


            "rooms":
                []

        }

    def roof_layout(
        self,
        room_program,
        unit
    ):


        rooms = []


        for room in room_program.get(
            "rooms",
            []
        ):


            room_type = room.get(
                "type"
            )


            if room_type == "stair_headroom":

                rooms.append({

                    "type":
                        "stair_headroom",

                    "location":
                        "roof"

                })


            elif room_type == "elevator_room":

                rooms.append({

                    "type":
                        "elevator_room",

                    "location":
                        "roof"

                })


            elif room_type == "parapet":

                rooms.append({

                    "type":
                        "parapet",

                    "height":
                        1.1,

                    "location":
                        "roof_boundary"

                })


        return {


            "unit":
                unit.get(
                    "id"
                ),


            "rooms":
                rooms,


            "rules":{


                "roof_access":
                    True,


                "parapet_required":
                    True

            }

        }

