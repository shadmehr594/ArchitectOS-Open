"""
ArchitectOS Building Placement Engine v1.0

Determines building position on site.

Features:
- Building placement side
- Coverage calculation
- Courtyard preservation
- L shape preparation
- Access points
- Multi-floor footprint
"""


class BuildingPlacementEngine:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"🏢 Building Placement Engine v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # BUILDING AREA
    # ==================================================

    def calculate_building_area(
        self,
        site_area,
        coverage
    ):

        return (
            site_area *
            coverage /
            100
        )


    # ==================================================
    # PLACEMENT
    # ==================================================

    def calculate_placement(
        self,
        site,
        request
    ):


        width = site.get(
            "width",
            0
        )

        depth = site.get(
            "depth",
            0
        )


        coverage = request.get(
            "coverage",
            60
        )


        building_side = request.get(
            "building_side",
            "south"
        )


        building_depth = (
            depth *
            coverage /
            100
        )


        return {


            "side":
                building_side,


            "footprint":
            {

                "x":0,

                "y":
                    0
                    if building_side in [
                        "south",
                        "west"
                    ]
                    else depth-building_depth,


                "width":
                    width,


                "depth":
                    building_depth

            }


        }



    # ==================================================
    # ACCESS
    # ==================================================

    def generate_access_points(
        self,
        road_side,
        request
    ):

        accesses = []


        if request.get(
            "commercial_access",
            False
        ):

            accesses.append(

                {

                    "type":
                        "commercial",

                    "side":
                        road_side,

                    "position":
                        "west"

                }

            )


        if request.get(
            "residential_access",
            False
        ):

            accesses.append(

                {

                    "type":
                        "residential",

                    "side":
                        road_side,

                    "position":
                        "center"

                }

            )


        if request.get(
            "parking_access",
            False
        ):

            accesses.append(

                {

                    "type":
                        "parking",

                    "side":
                        road_side,

                    "position":
                        "east"

                }

            )


        return accesses



    # ==================================================
    # MAIN
    # ==================================================

    def generate(
        self,
        site,
        request
    ):


        placement = self.calculate_placement(
            site,
            request
        )


        result = {


            "building":
                placement,


            "access_points":
                self.generate_access_points(

                    site.get(
                        "road_side",
                        "south"
                    ),

                    request

                ),


            "floors":
                request.get(
                    "floors",
                    1
                ),


            "coverage":
                request.get(
                    "coverage",
                    60
                )

        }


        print(
            "\n====== BUILDING PLACEMENT ======"
        )


        print(
            "SIDE:",
            placement["side"]
        )


        print(
            "FOOTPRINT:",
            placement["footprint"]
        )


        print(
            "ACCESS:",
            result["access_points"]
        )


        return result