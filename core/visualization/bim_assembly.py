class BIMAssembly:


    def __init__(self):

        print(
            "🏗️ BIM Assembly Engine v22.5 ACTIVE"
        )


    def assemble(
        self,
        rooms,
        walls,
        openings
    ):


        model = {

            "floors": {},

            "elements": {

                "rooms": [],

                "walls": [],

                "openings": []

            }

        }


        # ----------------------
        # Rooms
        # ----------------------

        for floor, data in rooms.get(
            "floors",
            {}
        ).items():

            model["floors"][floor] = {

                "rooms":
                    len(
                        data.get(
                            "rooms",
                            []
                        )
                    )

            }


            for room in data.get(
                "rooms",
                []
            ):

                model["elements"]["rooms"].append(
                    {
                        "floor": floor,
                        "name": room.get(
                            "name"
                        ),
                        "geometry": {

                            "x": room.get("x"),
                            "y": room.get("y"),
                            "width": room.get("width"),
                            "depth": room.get("depth")

                        }
                    }
                )


        # ----------------------
        # Walls
        # ----------------------

        for wall in walls.get(
            "walls",
            []
        ):

            model["elements"]["walls"].append(
                wall
            )


        # ----------------------
        # Openings
        # ----------------------

        for opening in openings.get(
            "openings",
            []
        ):

            model["elements"]["openings"].append(
                opening
            )


        return {

            "engine":
                "bim_assembly_v22.5",

            "status":
                "assembled",

            "model":
                model,

            "statistics":{

                "rooms":
                    len(
                        model["elements"]["rooms"]
                    ),

                "walls":
                    len(
                        model["elements"]["walls"]
                    ),

                "openings":
                    len(
                        model["elements"]["openings"]
                    )

            }

        }