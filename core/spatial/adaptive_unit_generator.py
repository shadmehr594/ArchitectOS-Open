"""
ArchitectOS Adaptive Unit Generator v1.0

Generates residential unit logic.
"""


class AdaptiveUnitGenerator:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🏠 Adaptive Unit Generator v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # ROOM SIZE
    # ==================================================

    def calculate_rooms(
        self,
        area,
        bedrooms
    ):


        rooms = []


        living_area = area * 0.35


        rooms.append({

            "type":
                "living",

            "area":
                round(
                    living_area,
                    2
                )

        })



        bedroom_area = (

            area * 0.35

            /

            bedrooms

        )



        for i in range(
            bedrooms
        ):


            rooms.append({

                "type":
                    "bedroom",

                "id":
                    f"bedroom_{i+1}",

                "area":
                    round(
                        bedroom_area,
                        2
                    )

            })



        rooms.append({

            "type":
                "kitchen",

            "area":
                round(
                    area * 0.12,
                    2
                )

        })



        rooms.append({

            "type":
                "bathroom",

            "area":
                round(
                    area * 0.08,
                    2
                )

        })



        return rooms



    # ==================================================
    # ADAPT
    # ==================================================

    def generate(
        self,
        unit
    ):


        area = unit.get(
            "area",
            80
        )


        bedrooms = unit.get(
            "bedrooms",
            2
        )


        rooms = self.calculate_rooms(

            area,

            bedrooms

        )


        for room in rooms:


            if room["type"] == "bedroom":


                room["light_source"] = (

                    "lightwell"

                    if unit.get(
                        "lightwell_access",
                        False
                    )

                    else

                    "facade"

                )



            if room["type"] in [

                "kitchen",

                "bathroom"

            ]:


                room["ventilation"] = (

                    "duct"

                    if unit.get(
                        "duct_required",
                        True
                    )

                    else

                    "natural"

                )



        return {


            "id":
                unit.get(
                    "id",
                    "unit_1"
                ),


            "type":
                unit.get(
                    "unit_type",
                    "residential"
                ),


            "area":
                area,


            "rooms":
                rooms

        }