"""
ArchitectOS Lightwell Engine v1.0

Decision layer for internal lightwells.

Features:
- Optional lightwell
- Residential aware
- Commercial / parking bypass
- User configurable dimensions
- Multi-unit support
"""


class LightwellEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"☀️ Lightwell Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # REQUIREMENT CHECK
    # ==================================================

    def needs_lightwell(
        self,
        floor
    ):


        if not floor.get(
            "enabled",
            True
        ):

            return False



        usage = floor.get(
            "usage",
            ""
        )


        if usage in [

            "commercial",

            "parking",

            "storage"

        ]:

            return False



        if usage == "residential":

            return True



        return floor.get(
            "force",
            False
        )



    # ==================================================
    # CREATE DECISION
    # ==================================================

    def generate(
        self,
        building,
        floors,
        user_settings=None
    ):


        user_settings = user_settings or {}



        result = []



        default = {

            "width":3,

            "depth":4,

            "area":12,

            "count":1,

            "access":"corridor"

        }



        default.update(
            user_settings
        )



        for floor in floors:


            if not self.needs_lightwell(
                floor
            ):

                result.append({

                    "floor":
                        floor.get(
                            "name"
                        ),

                    "required":
                        False

                })

                continue



            units = floor.get(
                "units",
                1
            )


            count = default["count"]



            if units >= 6:

                count = max(
                    count,
                    2
                )



            result.append({

                "floor":
                    floor.get(
                        "name"
                    ),

                "required":
                    True,

                "count":
                    count,

                "width":
                    default["width"],

                "depth":
                    default["depth"],

                "area":
                    default["area"],

                "access":
                    default["access"]

            })



        return {

            "lightwells":
                result

        }