"""
ArchitectOS Spatial Lightwell Aware Layout v1.0
"""


class LightwellAwareLayout:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🧩 Spatial Lightwell Aware Layout v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # CHECK VOID
    # ==================================================

    def is_inside_lightwell(
        self,
        point,
        lightwell
    ):


        x, y = point


        xs = [
            p[0]
            for p in lightwell
        ]


        ys = [
            p[1]
            for p in lightwell
        ]


        return (

            min(xs) <= x <= max(xs)

            and

            min(ys) <= y <= max(ys)

        )



    # ==================================================
    # CREATE SPACES
    # ==================================================

    def generate(
        self,
        building,
        lightwell,
        units=4
    ):


        result = {


            "lightwell":

            {

                "polygon":
                    lightwell,

                "access":
                    "corridor"

            },


            "spaces":[]

        }



        result["spaces"].append({

            "type":
                "corridor",

            "location":
                "adjacent_to_lightwell"

        })



        for i in range(
            units
        ):


            result["spaces"].append({

                "type":
                    "residential_unit",

                "id":
                    f"unit_{i+1}",

                "access_to_lightwell":
                    True

            })



        return result