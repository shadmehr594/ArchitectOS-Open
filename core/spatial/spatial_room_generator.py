"""
ArchitectOS Spatial Room Generator v1.1

Creates architectural rooms
with lightwell and ventilation logic.
"""


class SpatialRoomGenerator:


    VERSION = "1.1"



    def __init__(self):

        print(
            f"🏠 Spatial Room Generator v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # DUCT GENERATOR
    # ==================================================

    def create_ducts(
        self,
        separate=True
    ):


        if separate:

            return {

                "bathroom":
                    "duct_bathroom",

                "kitchen":
                    "duct_kitchen"

            }


        return {

            "bathroom":
                "shared_duct",

            "kitchen":
                "shared_duct"

        }



    # ==================================================
    # ROOM GENERATOR
    # ==================================================

    def generate_unit(
        self,
        unit_id,
        bedrooms=2,
        lightwell_access=True,
        separate_duct=True
    ):


        ducts = self.create_ducts(
            separate_duct
        )


        rooms = []


        rooms.append({

            "type":
                "living",

            "light_source":
                "main_facade"

        })


        for i in range(
            bedrooms
        ):

            rooms.append({

                "type":
                    "bedroom",

                "light_source":
                    (
                        "lightwell"
                        if lightwell_access
                        else
                        "main_facade"
                    )

            })



        rooms.append({

            "type":
                "bathroom",

            "ventilation":
                ducts["bathroom"]

        })


        rooms.append({

            "type":
                "kitchen",

            "ventilation":
                ducts["kitchen"]

        })


        return {

            "id":
                unit_id,

            "rooms":
                rooms

        }



    # ==================================================
    # BUILDING
    # ==================================================

    def generate(
        self,
        units=4,
        bedrooms=2,
        lightwell=True,
        separate_duct=True
    ):


        result = {


            "units":[],

            "rules":

            {

                "window_facing":
                    False

            }

        }


        for i in range(
            units
        ):


            result["units"].append(

                self.generate_unit(

                    f"unit_{i+1}",

                    bedrooms,

                    lightwell,

                    separate_duct

                )

            )


        return result