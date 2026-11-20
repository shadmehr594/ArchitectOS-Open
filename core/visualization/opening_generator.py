class OpeningGenerator:


    def __init__(self):

        print(
            "🚪 Opening Generator Engine v22.4 ACTIVE"
        )


    def generate(
        self,
        walls,
        rooms=None
    ):


        openings = []


        for wall in walls.get(
            "walls",
            []
        ):

            room = wall.get(
                "room"
            )

            floor = wall.get(
                "floor"
            )


            wall_list = wall.get(
                "walls",
                []
            )


            for w in wall_list:


                side = w.get(
                    "side"
                )


                # ------------------
                # Door Logic
                # ------------------

                if (
                    side == "south"
                    and room in [
                        "entrance",
                        "parking"
                    ]
                ):

                    openings.append(
                        {
                            "type":"door",
                            "floor":floor,
                            "room":room,
                            "side":side,
                            "width":1.2
                        }
                    )


                # ------------------
                # Window Logic
                # ------------------

                elif side in [
                    "north",
                    "east",
                    "west"
                ]:

                    openings.append(
                        {
                            "type":"window",
                            "floor":floor,
                            "room":room,
                            "side":side,
                            "width":1.5
                        }
                    )


        return {

            "engine":
                "opening_generator_v22.4",

            "status":
                "generated",

            "openings":
                openings
        }