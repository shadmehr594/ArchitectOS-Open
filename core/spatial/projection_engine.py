"""
ArchitectOS Projection Engine v1.0

Creates building projections
on selected sides.
"""


class ProjectionEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"📐 Projection Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # CREATE PROJECTION
    # ==================================================

    def create_projection(
        self,
        polygon,
        side,
        width,
        depth
    ):


        xs = [
            p[0]
            for p in polygon
        ]


        ys = [
            p[1]
            for p in polygon
        ]


        min_x = min(xs)

        max_x = max(xs)

        min_y = min(ys)

        max_y = max(ys)



        result = polygon.copy()



        # ----------------------------------
        # SOUTH
        # ----------------------------------

        if side == "south":


            x1 = min_x


            x2 = min_x + width



            result = [

                [x1, min_y - depth],

                [x2, min_y - depth],

                [x2, min_y],

                [x1, min_y]

            ]



        # ----------------------------------
        # NORTH
        # ----------------------------------

        elif side == "north":


            x1 = min_x


            x2 = min_x + width



            result = [

                [x1, max_y],

                [x2, max_y],

                [x2, max_y + depth],

                [x1, max_y + depth]

            ]



        # ----------------------------------
        # EAST
        # ----------------------------------

        elif side == "east":


            y1 = min_y


            y2 = min_y + width



            result = [

                [max_x, y1],

                [max_x + depth, y1],

                [max_x + depth, y2],

                [max_x, y2]

            ]



        # ----------------------------------
        # WEST
        # ----------------------------------

        elif side == "west":


            y1 = min_y


            y2 = min_y + width



            result = [

                [min_x - depth, y1],

                [min_x, y1],

                [min_x, y2],

                [min_x - depth, y2]

            ]



        return result



    # ==================================================
    # APPLY TO FLOOR
    # ==================================================

    def apply(
        self,
        floor,
        projection
    ):


        if not projection.get(
            "enabled",
            False
        ):


            return floor



        return {


            "level":
                floor.get(
                    "level"
                ),


            "polygon":
                self.create_projection(

                    floor["polygon"],

                    projection["side"],

                    projection["width"],

                    projection["depth"]

                ),


            "projection":
                projection

        }