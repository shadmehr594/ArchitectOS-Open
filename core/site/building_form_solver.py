"""
ArchitectOS Building Form Solver v1.0

Creates architectural building footprint
from site constraints.

Features:
- Optional parameters
- Coverage control
- Building placement side
- Courtyard integration
- Length compensation
- Projection separation
"""


class BuildingFormSolver:


    VERSION = "1.0"


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
    # COVERAGE
    # ==================================================

    def allowed_coverage_area(
        self,
        site,
        coverage
    ):

        area = self.site_area(
            site
        )


        return (

            area *

            coverage /

            100

        )



    # ==================================================
    # COURTYARD REDUCTION
    # ==================================================

    def apply_courtyard(
        self,
        site,
        courtyard
    ):


        if not courtyard:

            return {

                "width":
                    site.get(
                        "width",
                        0
                    ),

                "depth":
                    site.get(
                        "depth",
                        0
                    )

            }



        side = courtyard.get(
            "side",
            "north"
        )


        depth = courtyard.get(
            "depth",
            0
        )


        width = site.get(
            "width",
            0
        )


        site_depth = site.get(
            "depth",
            0
        )


        if side in [
            "north",
            "south"
        ]:


            return {

                "width":
                    width,

                "depth":
                    site_depth - depth

            }



        return {

            "width":
                width - depth,

            "depth":
                site_depth

        }



    # ==================================================
    # FOOTPRINT SOLVER
    # ==================================================

    def solve_footprint(
        self,
        site,
        request
    ):


        coverage = request.get(
            "coverage",
            100
        )


        max_area = self.allowed_coverage_area(

            site,

            coverage

        )


        courtyard = request.get(
            "courtyard",
            None
        )


        available = self.apply_courtyard(

            site,

            courtyard

        )


        width = available["width"]

        depth = available["depth"]



        # optional length compensation

        compensation = request.get(
            "length_compensation",
            {}
        )


        if compensation.get(
            "enabled",
            False
        ):


            depth += compensation.get(
                "extra_length",
                0
            )



        area = width * depth



        # coverage protection

        if area > max_area:


            depth = max_area / width

            area = width * depth



        return {


            "width":
                width,


            "depth":
                depth,


            "area":
                area

        }



    # ==================================================
    # PLACEMENT
    # ==================================================

    def create_polygon(
        self,
        site,
        footprint,
        side
    ):


        w = footprint["width"]

        d = footprint["depth"]


        sw = site.get(
            "width",
            0
        )


        sd = site.get(
            "depth",
            0
        )



        if side == "north":


            y = sd - d


            return [

                [0, y],

                [w, y],

                [w, sd],

                [0, sd]

            ]



        if side == "south":


            return [

                [0,0],

                [w,0],

                [w,d],

                [0,d]

            ]



        if side == "east":


            return [

                [sw-d,0],

                [sw,0],

                [sw,w],

                [sw-d,w]

            ]



        return [

            [0,0],

            [w,0],

            [w,d],

            [0,d]

        ]



    # ==================================================
    # MAIN
    # ==================================================

    def solve(
        self,
        site,
        request
    ):


        # ==================================================
        # PLACEMENT DECISION
        # ==================================================

        placement = request.get(
            "placement_side"
        )


        if placement is None:

            placement = request.get(
                "placement"
            )


        if placement is None:

            courtyard = request.get(
                "courtyard",
                {}
            )


            courtyard_side = courtyard.get(
                "side"
            )


            if courtyard_side in [
                "north",
                "south",
                "east",
                "west"
            ]:

                placement = courtyard_side


            else:

                placement = "center"


        footprint = self.solve_footprint(

            site,

            request

        )


        polygon = self.create_polygon(

            site,

            footprint,

            placement

        )



        projection = request.get(
            "projection",
            {

                "enabled": False,

                "side": None,

                "depth": 0

            }

        )



        result = {


            "building":

            {


                "footprint":

                {

                    "polygon":
                        polygon,

                    "area":
                        footprint["area"],

                    "coverage":
                        (

                            footprint["area"]

                            /

                            self.site_area(site)

                            *

                            100

                        )

                },


                "projection":
                    projection,


                "placement":
                    placement

            }

        }



        print(
            "\n====== BUILDING FORM ======"
        )


        print(
            "PLACEMENT:",
            placement
        )


        print(
            "AREA:",
            footprint["area"]
        )


        print(
            "COVERAGE:",
            result["building"]["footprint"]["coverage"]
        )


        print(
            "POLYGON:",
            polygon
        )


        return result