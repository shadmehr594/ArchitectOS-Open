"""
ArchitectOS Building Form Solver v2.4

Courtyard integrated footprint generator.

Features:
- Courtyard aware
- Coverage control
- North/South courtyard support
- Real footprint area
"""


class BuildingFormSolverV24:


    VERSION = "2.4"



    def __init__(self):

        print(
            f"🏢 Building Form Solver v{self.VERSION} ACTIVE"
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
    # COURTYARD
    # ==================================================

    def create_courtyard(
        self,
        site,
        courtyard
    ):


        if not courtyard.get(
            "enabled",
            False
        ):

            return None



        side = courtyard.get(
            "side",
            "north"
        )


        position = courtyard.get(
            "position",
            "west"
        )


        width = courtyard.get(
            "width",
            0
        )


        depth = courtyard.get(
            "depth",
            0
        )



        sw = site["width"]

        sd = site["depth"]



        if side == "north":


            x = 0


            if position == "east":

                x = sw - width



            return [

                [x, sd-depth],

                [x+width, sd-depth],

                [x+width, sd],

                [x, sd]

            ]



        if side == "south":


            x = 0


            if position == "east":

                x = sw-width



            return [

                [x,0],

                [x+width,0],

                [x+width,depth],

                [x,depth]

            ]



        return None



    # ==================================================
    # FOOTPRINT
    # ==================================================

    def create_building(
        self,
        site,
        request
    ):


        coverage = request.get(
            "coverage",
            100
        )


        target_area = (

            site["width"]

            *

            site["depth"]

            *

            coverage

            /

            100

        )


        placement = request.get(
            "placement",
            "south"
        )



        depth = (

            target_area

            /

            site["width"]

        )



        if placement == "north":


            y = site["depth"] - depth


            return [

                [0,y],

                [site["width"],y],

                [site["width"],site["depth"]],

                [0,site["depth"]]

            ]



        return [

            [0,0],

            [site["width"],0],

            [site["width"],depth],

            [0,depth]

        ]



    # ==================================================
    # SOLVE
    # ==================================================

    def solve(
        self,
        site,
        request
    ):


        courtyard = self.create_courtyard(

            site,

            request.get(
                "courtyard",
                {}
            )

        )


        building = self.create_building(

            site,

            request

        )


        area = self.polygon_area(
            building
        )


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
                        building,

                    "area":
                        area,

                    "coverage":
                        coverage

                }

            },


            "courtyard":

            {

                "polygon":
                    courtyard

            }

        }



        print(
            "\n====== BUILDING FORM V2.4 ======"
        )


        print(
            "BUILDING AREA:",
            area
        )


        print(
            "COVERAGE:",
            coverage
        )


        print(
            "COURTYARD:",
            courtyard
        )



        return result