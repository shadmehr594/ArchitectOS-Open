"""
ArchitectOS Setback Engine v1.0

Calculates buildable zone
after site setbacks.

Input:
- Site boundary
- Neighbor analysis

Output:
- Buildable boundary
- Setback values
- Buildable area
"""


class SetbackEngine:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"📏 Setback Engine v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # AREA
    # ==================================================

    def polygon_area(
        self,
        points
    ):

        if len(points) < 3:

            return 0


        area = 0


        for i in range(len(points)):

            x1, y1 = points[i]

            x2, y2 = points[
                (i + 1) % len(points)
            ]


            area += (
                x1 * y2 -
                x2 * y1
            )


        return abs(area) / 2



    # ==================================================
    # SETBACK RULES
    # ==================================================

    def calculate_setbacks(
        self,
        neighbors
    ):


        setbacks = {

            "north": 2,

            "south": 3,

            "east": 2,

            "west": 2

        }


        # shared wall condition

        if neighbors.get(
            "east",
            {}
        ).get(
            "shared_wall",
            False
        ):

            setbacks["east"] = 0



        if neighbors.get(
            "west",
            {}
        ).get(
            "shared_wall",
            False
        ):

            setbacks["west"] = 0



        # road side

        if neighbors.get(
            "south",
            {}
        ).get(
            "access",
            False
        ):

            setbacks["south"] = 3



        return setbacks



    # ==================================================
    # BUILDABLE RECTANGLE
    # ==================================================

    def create_buildable_boundary(
        self,
        boundary,
        setbacks
    ):


        xs = [

            p[0]

            for p in boundary

        ]


        ys = [

            p[1]

            for p in boundary

        ]


        min_x = min(xs)

        max_x = max(xs)

        min_y = min(ys)

        max_y = max(ys)



        return [

            [

                min_x + setbacks["west"],

                min_y + setbacks["south"]

            ],


            [

                max_x - setbacks["east"],

                min_y + setbacks["south"]

            ],


            [

                max_x - setbacks["east"],

                max_y - setbacks["north"]

            ],


            [

                min_x + setbacks["west"],

                max_y - setbacks["north"]

            ]

        ]



    # ==================================================
    # MAIN
    # ==================================================

    def analyze(
        self,
        site,
        neighbors
    ):


        boundary = site.get(
            "boundary",
            []
        )


        setbacks = self.calculate_setbacks(
            neighbors
        )


        buildable_boundary = self.create_buildable_boundary(
            boundary,
            setbacks
        )


        result = {

            "setbacks":
                setbacks,


            "buildable_boundary":
                buildable_boundary,


            "buildable_area":
                self.polygon_area(
                    buildable_boundary
                )

        }


        print(
            "\n====== SETBACK ANALYSIS ======"
        )


        print(
            "SETBACKS:",
            setbacks
        )


        print(
            "BUILDABLE AREA:",
            result["buildable_area"]
        )


        return result