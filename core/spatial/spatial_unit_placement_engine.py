"""
ArchitectOS Spatial Unit Placement Engine v1.0

Places residential units inside floor layout.
"""


class SpatialUnitPlacementEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🏠 Spatial Unit Placement Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # CREATE UNIT
    # ==================================================

    def create_unit(
        self,
        unit_id,
        x,
        y,
        width,
        depth
    ):


        polygon = [

            [x, y],

            [x + width, y],

            [x + width, y + depth],

            [x, y + depth]

        ]



        return {


            "id":
                unit_id,


            "polygon":
                polygon,


            "area":
                width * depth,


            "adjacent":

            [

                "corridor",

                "lightwell"

            ],


            "rooms":

            [

                {

                    "type":
                        "living",

                    "light":
                        "facade"

                },


                {

                    "type":
                        "bedroom",

                    "light":
                        "lightwell"

                },


                {

                    "type":
                        "kitchen",

                    "ventilation":
                        "duct"

                },


                {

                    "type":
                        "bathroom",

                    "ventilation":
                        "duct"

                }

            ]

        }



    # ==================================================
    # RESIDENTIAL FLOOR
    # ==================================================

    def generate(
        self,
        floor,
        unit_count
    ):


        units = []



        width = 8

        depth = 10



        for i in range(
            unit_count
        ):


            units.append(

                self.create_unit(

                    f"unit_{i+1}",

                    i * width,

                    0,

                    width,

                    depth

                )

            )



        return {


            "level":
                floor.get(
                    "level"
                ),


            "units":
                units

        }