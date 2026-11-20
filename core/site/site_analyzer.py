"""
ArchitectOS Site Analyzer v1.1

Analyzes site context before spatial design.

Features:
- Boundary analysis
- Edge orientation
- Road detection
- Neighbor detection
- Buildable zone preparation
- Support SiteModel and dict input
"""


import math



class SiteAnalyzer:


    VERSION = "1.1"



    def __init__(self):

        print(
            f"🌍 Site Analyzer v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # SITE NORMALIZER
    # ==================================================

    def normalize_site(
        self,
        site
    ):


        if isinstance(
            site,
            dict
        ):

            boundary = site.get(
                "boundary",
                []
            )

            roads = site.get(
                "roads",
                []
            )

            neighbors = site.get(
                "neighbors",
                []
            )


            area = self.calculate_area(
                boundary
            )


            return {

                "boundary":
                    boundary,

                "roads":
                    roads,

                "neighbors":
                    neighbors,

                "area":
                    area

            }



        return {

            "boundary":
                site.boundary,

            "roads":
                site.roads,

            "neighbors":
                getattr(
                    site,
                    "neighbors",
                    []
                ),

            "area":
                site.area_estimate()

        }



    # ==================================================
    # AREA
    # ==================================================

    def calculate_area(
        self,
        boundary
    ):


        if len(boundary) < 3:

            return 0



        area = 0



        for i in range(
            len(boundary)
        ):


            x1, y1 = boundary[i]

            x2, y2 = boundary[
                (i + 1) % len(boundary)
            ]

            area += (

                x1 * y2 -

                x2 * y1

            )



        return abs(area) / 2



    # ==================================================
    # CENTROID
    # ==================================================

    def calculate_centroid(
        self,
        boundary
    ):


        if not boundary:

            return [
                0,
                0
            ]



        x = 0

        y = 0



        for point in boundary:

            x += point[0]

            y += point[1]



        count = len(
            boundary
        )



        return [

            x / count,

            y / count

        ]



    # ==================================================
    # EDGE LENGTH
    # ==================================================

    def edge_length(
        self,
        p1,
        p2
    ):


        return math.sqrt(

            (p2[0] - p1[0]) ** 2 +

            (p2[1] - p1[1]) ** 2

        )



    # ==================================================
    # EDGE DIRECTION
    # ==================================================

    def edge_direction(
        self,
        p1,
        p2
    ):


        dx = p2[0] - p1[0]

        dy = p2[1] - p1[1]



        angle = math.degrees(

            math.atan2(
                dy,
                dx
            )

        )



        if angle < 0:

            angle += 360



        return angle



    # ==================================================
    # BOUNDARY ANALYSIS
    # ==================================================

    def analyze_boundary(
        self,
        boundary
    ):


        edges = []



        for i in range(
            len(boundary)
        ):


            p1 = boundary[i]

            p2 = boundary[
                (i + 1) % len(boundary)
            ]



            edges.append(

                {

                    "start":
                        p1,

                    "end":
                        p2,

                    "length":
                        self.edge_length(
                            p1,
                            p2
                        ),

                    "angle":
                        self.edge_direction(
                            p1,
                            p2
                        )

                }

            )



        return edges



    # ==================================================
    # ROAD ANALYSIS
    # ==================================================

    def detect_access_side(
        self,
        roads
    ):


        if not roads:

            return None



        main = roads[0]



        return {

            "side":
                main.get(
                    "side"
                ),

            "type":
                main.get(
                    "type",
                    "road"
                )

        }



    # ==================================================
    # BUILDABLE AREA
    # ==================================================

    def create_buildable_zone(
        self,
        boundary
    ):


        return {

            "boundary":
                boundary,

            "status":
                "raw",

            "setback_applied":
                False

        }



    # ==================================================
    # MAIN ANALYSIS
    # ==================================================

    def analyze(
        self,
        site
    ):


        data = self.normalize_site(
            site
        )


        boundary = data["boundary"]

        roads = data["roads"]

        neighbors = data["neighbors"]



        result = {


            "site":

            {

                "area":
                    data["area"],


                "centroid":
                    self.calculate_centroid(
                        boundary
                    )

            },


            "boundary":

                self.analyze_boundary(
                    boundary
                ),



            "access":

                self.detect_access_side(
                    roads
                ),



            "neighbors":

                neighbors,



            "buildable_zone":

                self.create_buildable_zone(
                    boundary
                )


        }



        print(
            "\n====== SITE ANALYSIS ======"
        )


        print(
            "AREA:",
            result["site"]["area"]
        )


        print(
            "CENTROID:",
            result["site"]["centroid"]
        )


        print(
            "ACCESS:",
            result["access"]
        )


        print(
            "NEIGHBORS:",
            len(
                neighbors
            )
        )



        return result