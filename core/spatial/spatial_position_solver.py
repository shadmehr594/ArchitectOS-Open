"""
ArchitectOS Spatial Position Solver v1.0

Converts semantic spatial intent
(zone / position / order)
into geometric coordinates.
"""


class SpatialPositionSolver:


    VERSION = "1.0"



    def __init__(self):

        print(
            "📐 SPATIAL POSITION SOLVER v1.0 ONLINE"
        )



    # ==================================================
    # DEFAULT SPACE DIMENSIONS
    # ==================================================

    def resolve_size(
        self,
        space
    ):

        name = space.get(
            "name",
            ""
        )


        sizes = {


            "living":
                (5, 4),


            "kitchen":
                (3, 3),


            "dining":
                (3, 3),


            "bedroom":
                (4, 4),


            "master_bedroom":
                (5, 4),


            "bathroom":
                (2, 3),


            "stairs":
                (3, 3),


            "entrance":
                (3, 2),


            "guest_room":
                (3, 3),


            "family_lounge":
                (4, 3)

        }



        return sizes.get(
            name,
            (3,3)
        )



    # ==================================================
    # POSITION RULES
    # ==================================================

    def resolve_origin(
        self,
        position,
        index,
        width,
        height
    ):


        if position == "front":

            return (

                index * width,

                0

            )


        if position == "rear":

            return (

                index * width,

                height * 2

            )


        if position == "center":

            return (

                index * width,

                height

            )


        if position == "service":

            return (

                0,

                index * height

            )


        if position == "garden":

            return (

                index * width,

                -height

            )


        return (

            index * width,

            index * height

        )



    # ==================================================
    # SOLVE FLOOR
    # ==================================================

    def solve_floor(
        self,
        floor
    ):


        result = []


        spaces = floor.get(
            "spaces",
            []
        )


        for index, space in enumerate(spaces):


            width, height = self.resolve_size(
                space
            )


            x, y = self.resolve_origin(

                space.get(
                    "position"
                ),

                index,

                width,

                height

            )


            result.append(

                {

                    **space,


                    "x":
                        x,


                    "y":
                        y,


                    "width":
                        width,


                    "height":
                        height


                }

            )


        return result



    # ==================================================
    # SOLVE BUILDING
    # ==================================================

    def solve(
        self,
        spatial
    ):


        output = {}


        for level, floor in spatial.items():


            output[level] = {


                "level":
                    level,


                "spaces":
                    self.solve_floor(
                        floor
                    )


            }



        return output