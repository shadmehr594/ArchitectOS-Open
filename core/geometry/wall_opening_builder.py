class WallOpeningBuilder:


    def __init__(self):

        print(
            "🧱 Wall & Opening Parametric Builder v27.3 ACTIVE"
        )



    def build(
        self,
        envelope,
        config=None
    ):


        config = config or {}


        dimensions = config.get(
            "building",
            {}
        )


        width = dimensions.get(
            "width",
            10
        )


        depth = dimensions.get(
            "depth",
            10
        )


        height = dimensions.get(
            "floor_height",
            3
        )


        thickness = config.get(
            "wall_thickness",
            0.20
        )



        walls = []

        openings = []



        # ----------------------
        # Facade walls
        # ----------------------

        facades = [

            ("north", width),

            ("south", width),

            ("east", depth),

            ("west", depth)

        ]



        for facade, length in facades:


            walls.append(

                {

                    "facade":
                    facade,


                    "type":
                    "exterior_wall",


                    "length":
                    length,


                    "height":
                    height,


                    "thickness":
                    thickness

                }

            )



        # ----------------------
        # Openings
        # ----------------------

        for facade, data in envelope.items():


            for opening in data.get(
                "openings",
                []
            ):


                openings.append(

                    {

                        "facade":
                        facade,


                        "type":
                        opening.get(
                            "type",
                            "window"
                        ),


                        "width":
                        opening.get(
                            "width",
                            1.5
                        ),


                        "height":
                        opening.get(
                            "height",
                            1.5
                        ),


                        "position":
                        "center"

                    }

                )



        return {


            "engine":
            "wall_opening_builder_v27.3",


            "status":
            "generated",


            "walls":
            walls,


            "openings":
            openings,


            "statistics":
            {

                "walls":
                len(walls),


                "openings":
                len(openings)

            }

        }