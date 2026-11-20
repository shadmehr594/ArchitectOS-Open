"""
ArchitectOS Lightwell Geometry Engine v1.0

Creates real lightwell openings
inside building footprint.
"""


class LightwellGeometryEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"☀️ Lightwell Geometry Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # CREATE LIGHTWELL POLYGON
    # ==================================================

    def create_lightwell_polygon(
        self,
        building,
        lightwell
    ):


        width = lightwell.get(
            "width",
            3
        )


        depth = lightwell.get(
            "depth",
            4
        )


        position = lightwell.get(
            "position",
            "center"
        )


        xs = [

            p[0]

            for p in building

        ]


        ys = [

            p[1]

            for p in building

        ]


        min_x = min(xs)

        max_x = max(xs)

        min_y = min(ys)

        max_y = max(ys)



        if position == "center":


            x = (

                min_x

                +

                max_x

            ) / 2 - width / 2



            y = (

                min_y

                +

                max_y

            ) / 2 - depth / 2



        else:


            x = min_x

            y = min_y



        return [

            [x,y],

            [x+width,y],

            [x+width,y+depth],

            [x,y+depth]

        ]



    # ==================================================
    # SOLVE
    # ==================================================

    def solve(
        self,
        building_polygon,
        lightwell_decision
    ):


        openings = []



        if not lightwell_decision.get(
            "required",
            False
        ):

            return {

                "building_polygon":
                    building_polygon,

                "lightwells":
                    []

            }



        count = lightwell_decision.get(
            "count",
            1
        )


        for i in range(count):


            lw = self.create_lightwell_polygon(

                building_polygon,

                lightwell_decision

            )


            openings.append(
                lw
            )



        return {


            "building_polygon":
                building_polygon,


            "lightwells":
                openings

        }