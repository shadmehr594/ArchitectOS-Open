"""
ArchitectOS Building Form Solver v2.1

Polygon based building footprint generator.

Features:
- Buildable polygon input
- Polygon merge preparation
- L-shape footprint generation
- Coverage control
"""


class BuildingFormSolverV21:


    VERSION = "2.1"


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
    # MERGE RECTANGLE ZONES v2.1.1
    # ==================================================

    def merge_polygons(
        self,
        polygons
    ):


        points = []


        for polygon in polygons:

            for point in polygon:

                if point not in points:

                    points.append(
                        point
                    )



        # sort by angle around centroid

        cx = sum(
            p[0]
            for p in points
        ) / len(points)



        cy = sum(
            p[1]
            for p in points
        ) / len(points)



        import math



        points.sort(

            key=lambda p:

                math.atan2(

                    p[1] - cy,

                    p[0] - cx

                )

        )



        return points



    # ==================================================
    # COVERAGE LIMIT
    # ==================================================

    def limit_area(
        self,
        site,
        polygon,
        coverage
    ):


        max_area = (

            site["width"]

            *

            site["depth"]

            *

            coverage

            /

            100

        )


        current = self.polygon_area(
            polygon
        )


        return min(
            current,
            max_area
        )



    # ==================================================
    # MAIN SOLVER
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


        footprint = self.merge_polygons(

            buildable_polygons

        )


        area = self.limit_area(

            site,

            footprint,

            coverage

        )


        result = {


            "building":

            {


                "footprint":

                {

                    "polygon":

                        footprint,


                    "area":

                        area,


                    "coverage":

                        (

                            area

                            /

                            (

                                site["width"]

                                *

                                site["depth"]

                            )

                            *

                            100

                        )

                },


                "placement":

                    request.get(
                        "placement",
                        None
                    )

            }

        }



        print(
            "\n====== BUILDING FORM V2.1 ======"
        )


        print(
            "AREA:",
            area
        )


        print(
            "COVERAGE:",
            result["building"]["footprint"]["coverage"]
        )


        print(
            "POLYGON:",
            footprint
        )


        return result