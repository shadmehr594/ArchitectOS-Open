"""
ArchitectOS Courtyard Engine v3.0

Generates configurable open spaces inside a site.

Features:
- North / South / East / West courtyard
- Position control
- Width / Depth parameter
- Polygon generation
- Remaining site preparation
"""


class CourtyardEngine:


    VERSION = "3.0"


    def __init__(self):

        print(
            f"🌿 Courtyard Engine v{self.VERSION} ACTIVE"
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
    # COURTYARD AREA
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

                x1 * y2 -

                x2 * y1

            )


        return abs(area) / 2



    # ==================================================
    # COURTYARD POLYGON
    # ==================================================

    def create_courtyard(
        self,
        site,
        request
    ):


        width = request.get(
            "width"
        )


        depth = request.get(
            "depth",
            0
        )


        if width is None:

            area = request.get(
                "area",
                0
            )

            if depth > 0:

                width = area / depth

            else:

                width = 0


        side = request.get(
            "side",
            "north"
        )


        position = request.get(
            "position",
            "center"
        )


        site_width = site.get(
            "width",
            0
        )


        site_depth = site.get(
            "depth",
            0
        )



        # ------------------------------
        # NORTH
        # ------------------------------

        if side == "north":


            y1 = site_depth - depth

            y2 = site_depth


            if position == "west":

                x1 = 0


            elif position == "east":

                x1 = site_width - width


            else:

                x1 = (

                    site_width - width

                ) / 2



            return [

                [x1, y1],

                [x1 + width, y1],

                [x1 + width, y2],

                [x1, y2]

            ]



        # ------------------------------
        # SOUTH
        # ------------------------------

        if side == "south":


            y1 = 0

            y2 = depth


            if position == "west":

                x1 = 0


            elif position == "east":

                x1 = site_width - width


            else:

                x1 = (

                    site_width - width

                ) / 2



            return [

                [x1, y1],

                [x1 + width, y1],

                [x1 + width, y2],

                [x1, y2]

            ]



        # ------------------------------
        # EAST
        # ------------------------------

        if side == "east":


            x1 = site_width - depth

            x2 = site_width



            if position == "south":

                y1 = 0


            elif position == "north":

                y1 = site_depth - width


            else:

                y1 = (

                    site_depth - width

                ) / 2



            return [

                [x1, y1],

                [x2, y1],

                [x2, y1 + width],

                [x1, y1 + width]

            ]



        # ------------------------------
        # WEST
        # ------------------------------

        if side == "west":


            x1 = 0

            x2 = depth



            if position == "south":

                y1 = 0


            elif position == "north":

                y1 = site_depth - width


            else:

                y1 = (

                    site_depth - width

                ) / 2



            return [

                [x1, y1],

                [x2, y1],

                [x2, y1 + width],

                [x1, y1 + width]

            ]



    # ==================================================
    # MAIN
    # ==================================================

    def generate(
        self,
        site,
        requirement
    ):


        if not requirement.get(
            "enabled",
            True
        ):

            return {

                "courtyard": None,

                "remaining_site":

                    {

                    "type":
                        "full_site"

                    }

            }



        polygon = self.create_courtyard(

            site,

            requirement

        )


        area = self.polygon_area(

            polygon

        )


        result = {


            "courtyard":

            {

                "polygon":
                    polygon,

                "area":
                    area,

                "side":
                    requirement.get(
                        "side"
                    ),

                "position":
                    requirement.get(
                        "position"
                    ),

                "width":
                    requirement.get(
                        "width"
                    ),

                "depth":
                    requirement.get(
                        "depth"
                    )

            },


            "remaining_site":

            {

                "type":
                    "polygon_ready"

            }

        }



        print(
            "\n====== COURTYARD ANALYSIS ======"
        )


        print(
            "SIDE:",
            requirement.get(
                "side"
            )
        )


        print(
            "POSITION:",
            requirement.get(
                "position"
            )
        )


        print(
            "AREA:",
            area
        )


        print(
            "POLYGON:",
            polygon
        )


        return result