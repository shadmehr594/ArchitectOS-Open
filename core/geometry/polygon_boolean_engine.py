"""
ArchitectOS Polygon Boolean Engine v1.0

Handles architectural voids
inside building polygons.

Initial support:
- Lightwell subtraction
"""


class PolygonBooleanEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"📐 Polygon Boolean Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # AREA
    # ==================================================

    def polygon_area(
        self,
        polygon
    ):

        area = 0


        for i in range(
            len(polygon)
        ):

            x1, y1 = polygon[i]

            x2, y2 = polygon[
                (i + 1) %
                len(polygon)
            ]


            area += (

                x1 * y2

                -

                x2 * y1

            )


        return abs(area) / 2



    # ==================================================
    # SUBTRACT VOIDS
    # ==================================================

    def subtract(
        self,
        outer_polygon,
        voids
    ):


        outer_area = self.polygon_area(

            outer_polygon

        )


        void_area = 0


        for void in voids:


            void_area += self.polygon_area(

                void

            )



        solid_area = (

            outer_area

            -

            void_area

        )



        return {


            "outer_boundary":
                outer_polygon,


            "voids":
                voids,


            "solid_area":
                solid_area,


            "outer_area":
                outer_area,


            "void_area":
                void_area

        }