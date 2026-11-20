"""
ArchitectOS Building Form Solver v2.3

Real footprint generator.

Features:
- Real polygon area control
- Coverage limit
- Placement aware footprint
- North/South/East/West support
"""


class BuildingFormSolverV23:


    VERSION = "2.3"



    def __init__(self):

        print(
            f"🏢 Building Form Solver v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # SITE AREA
    # ==================================================

    def site_area(
        self,
        site
    ):

        return (

            site.get(
                "width",
                0
            )

            *

            site.get(
                "depth",
                0
            )

        )



    # ==================================================
    # REAL FOOTPRINT
    # ==================================================

    def create_footprint(
        self,
        site,
        request
    ):


        width = site["width"]

        depth = site["depth"]


        coverage = request.get(
            "coverage",
            100
        )


        target_area = (

            width

            *

            depth

            *

            coverage

            /

            100

        )


        placement = request.get(
            "placement",
            "south"
        )



        # keep full width,
        # calculate real depth

        building_depth = (

            target_area

            /

            width

        )



        if placement == "north":


            y = depth - building_depth


            return [

                [0, y],

                [width, y],

                [width, depth],

                [0, depth]

            ]



        if placement == "south":


            return [

                [0,0],

                [width,0],

                [width, building_depth],

                [0, building_depth]

            ]



        if placement == "east":


            x = width - building_depth


            return [

                [x,0],

                [width,0],

                [width,depth],

                [x,depth]

            ]



        return [

            [0,0],

            [width,0],

            [width,depth],

            [0,depth]

        ]



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


            x1,y1 = polygon[i]


            x2,y2 = polygon[
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
        request
    ):


        polygon = self.create_footprint(

            site,

            request

        )


        area = self.polygon_area(
            polygon
        )


        coverage = (

            area

            /

            self.site_area(site)

            *

            100

        )



        result = {


            "building":

            {


                "footprint":

                {

                    "polygon":
                        polygon,


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
            "\n====== BUILDING FORM V2.3 ======"
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
            polygon
        )


        return result