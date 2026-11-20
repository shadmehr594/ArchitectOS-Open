"""
ArchitectOS Building Form Solver v2.0

Creates building footprint
from buildable polygons.

Features:
- Polygon based input
- Coverage control
- L-shape preparation
- Courtyard aware footprint
"""


class BuildingFormSolverV2:


    VERSION = "2.0"



    def __init__(self):

        print(
            f"🏢 Building Form Solver v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # POLYGON AREA
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
    # BUILDABLE AREA
    # ==================================================

    def total_buildable_area(
        self,
        polygons
    ):


        total = 0


        for polygon in polygons:

            total += self.polygon_area(
                polygon
            )


        return total



    # ==================================================
    # COVERAGE
    # ==================================================

    def allowed_area(
        self,
        site,
        coverage
    ):


        return (

            site["width"]

            *

            site["depth"]

            *

            coverage

            /

            100

        )



    # ==================================================
    # FOOTPRINT SOLVER
    # ==================================================

    def solve(
        self,
        site,
        buildable_polygons,
        request
    ):


        coverage = request.get(

            "coverage",

            100

        )


        max_area = self.allowed_area(

            site,

            coverage

        )



        available_area = self.total_buildable_area(

            buildable_polygons

        )



        footprint_area = min(

            available_area,

            max_area

        )



        selected_polygon = buildable_polygons[0]



        result = {


            "building":

            {


                "footprint":

                {

                    "polygon":

                        selected_polygon,


                    "area":

                        footprint_area,


                    "coverage":

                        footprint_area

                        /

                        (

                            site["width"]

                            *

                            site["depth"]

                        )

                        *

                        100

                },


                "placement":

                    request.get(

                        "placement",

                        None

                    )

            }

        }



        print(

            "\n====== BUILDING FORM V2 ======"

        )


        print(

            "AREA:",

            footprint_area

        )


        print(

            "COVERAGE:",

            result["building"]["footprint"]["coverage"]

        )


        print(

            "POLYGON:",

            selected_polygon

        )


        return result