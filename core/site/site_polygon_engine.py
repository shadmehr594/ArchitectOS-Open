"""
ArchitectOS Site Polygon Engine v1.1

Generates buildable polygons
after removing courtyard/open spaces.

Features:
- Site boundary generation
- Courtyard subtraction
- Buildable zones
- Multiple polygon output preparation
"""


class SitePolygonEngine:


    VERSION = "1.1"



    def __init__(self):

        print(
            f"📐 Site Polygon Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # SITE BOUNDARY
    # ==================================================

    def create_site_polygon(
        self,
        site
    ):


        width = site.get(
            "width",
            0
        )


        depth = site.get(
            "depth",
            0
        )


        return [

            [0,0],

            [width,0],

            [width,depth],

            [0,depth]

        ]



    # ==================================================
    # NORTH / SOUTH COURTYARD
    # ==================================================

    def split_horizontal(
        self,
        site,
        courtyard
    ):


        polygon = courtyard.get(
            "polygon",
            []
        )


        if len(polygon) != 4:

            return []



        xs = [

            point[0]

            for point in polygon

        ]


        ys = [

            point[1]

            for point in polygon

        ]


        min_x = min(xs)

        max_x = max(xs)

        min_y = min(ys)

        max_y = max(ys)



        site_width = site.get(
            "width"
        )

        site_depth = site.get(
            "depth"
        )



        result = []



        # lower buildable zone

        if min_y > 0:


            result.append(

                [

                    [0,0],

                    [site_width,0],

                    [site_width,min_y],

                    [0,min_y]

                ]

            )



        # remaining upper strip

        if max_x < site_width:


            result.append(

                [

                    [max_x,min_y],

                    [site_width,min_y],

                    [site_width,max_y],

                    [max_x,max_y]

                ]

            )


        return result



    # ==================================================
    # MAIN
    # ==================================================

    def generate(
        self,
        site,
        courtyard=None
    ):


        site_polygon = self.create_site_polygon(

            site

        )


        if not courtyard:


            result = {

                "type":
                    "full_buildable_site",

                "site_polygon":
                    site_polygon,

                "buildable_polygons":
                    [

                        site_polygon

                    ]

            }


        else:


            buildable = self.split_horizontal(

                site,

                courtyard

            )


            result = {


                "type":
                    "site_with_open_space",


                "site_polygon":
                    site_polygon,


                "courtyard_polygon":
                    courtyard.get(
                        "polygon"
                    ),


                "buildable_polygons":
                    buildable

            }



        print(
            "\n====== SITE POLYGON ======"
        )


        print(
            "SITE:",
            site_polygon
        )


        if courtyard:

            print(
                "COURTYARD:",
                courtyard.get(
                    "polygon"
                )
            )


        print(
            "BUILDABLE:",
            result.get(
                "buildable_polygons"
            )
        )


        return result