"""
ArchitectOS Building Form Solver v2.2

Concave footprint generator.

Features:
- Clean polygon boundary
- Remove collinear points
- L-shape preparation
"""


class BuildingFormSolverV22:


    VERSION = "2.2"



    def __init__(self):

        print(
            f"🏢 Building Form Solver v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # REMOVE EXTRA POINTS
    # ==================================================

    def clean_polygon(
        self,
        polygon
    ):


        cleaned = []


        total = len(
            polygon
        )


        for i in range(total):

            prev = polygon[
                i - 1
            ]

            current = polygon[
                i
            ]

            nxt = polygon[
                (i + 1)
                %
                total
            ]



            dx1 = current[0] - prev[0]

            dy1 = current[1] - prev[1]


            dx2 = nxt[0] - current[0]

            dy2 = nxt[1] - current[1]



            cross = (

                dx1 * dy2

                -

                dy1 * dx2

            )



            if cross != 0:

                cleaned.append(
                    current
                )



        return cleaned



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
                (i+1)
                %
                len(polygon)
            ]


            area += (

                x1*y2

                -

                x2*y1

            )


        return abs(area)/2



    # ==================================================
    # SOLVE
    # ==================================================

    def solve(
        self,
        site,
        polygon,
        request
    ):


        cleaned = self.clean_polygon(
            polygon
        )


        area = self.polygon_area(
            cleaned
        )

        coverage_limit = request.get(
            "coverage",
            100
        )


        max_area = (

            site["width"]

            *

            site["depth"]

            *

            coverage_limit

            /

            100

        )


        if area > max_area:

            area = max_area


        coverage = (

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



        result = {


            "building":

            {

                "footprint":

                {

                    "polygon":
                        cleaned,


                    "area":
                        area,


                    "coverage":
                        coverage

                },


                "placement":

                    request.get(
                        "placement",
                        None
                    )

            }

        }



        print(
            "\n====== BUILDING FORM V2.2 ======"
        )


        print(
            "AREA:",
            area
        )


        print(
            "COVERAGE:",
            coverage
        )


        print(
            "POLYGON:",
            cleaned
        )


        return result