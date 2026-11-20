"""
ArchitectOS Spatial Floor Layout Engine v1.0

Places floor spaces spatially.
"""


class SpatialFloorLayoutEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🧩 Spatial Floor Layout Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # RESIDENTIAL LAYOUT
    # ==================================================

    def residential_layout(
        self,
        floor
    ):


        units = floor.get(
            "units",
            1
        )


        layout = []



        # -------------------------------
        # CORE
        # -------------------------------

        layout.append({

            "type":
                "core",

            "position":
                "center",

            "contains":
            [
                "stair",
                "elevator"
            ]

        })



        # -------------------------------
        # LIGHTWELL
        # -------------------------------

        layout.append({

            "type":
                "lightwell",

            "position":
                "center_adjacent"

        })



        # -------------------------------
        # UNITS
        # -------------------------------

        for i in range(
            units
        ):


            layout.append({

                "type":
                    "unit",

                "id":
                    f"unit_{i+1}",

                "access":
                    "corridor",

                "lightwell_access":
                    True

            })



        # -------------------------------
        # CORRIDOR
        # -------------------------------

        layout.append({

            "type":
                "corridor",

            "position":
                "central"

        })



        return {


            "level":
                floor.get(
                    "level"
                ),


            "type":
                "residential",


            "layout":
                layout

        }



    # ==================================================
    # MAIN
    # ==================================================

    def generate(
        self,
        floor
    ):


        if floor.get(
            "type"
        ) == "residential":


            return self.residential_layout(
                floor
            )


        return {


            "level":
                floor.get(
                    "level"
                ),


            "type":
                floor.get(
                    "type"
                ),


            "layout":[]

        }