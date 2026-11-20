class WallGenerator:

    def __init__(self):
        print("🧱 Wall Generator Engine v22.3 ACTIVE")


    def generate(self, drawing):

        walls = []

        floors = drawing.get(
            "floors",
            {}
        )


        for floor_name, floor_data in floors.items():

            rooms = floor_data.get(
                "rooms",
                []
            )


            for room in rooms:

                x = room["x"]
                y = room["y"]
                w = room["width"]
                d = room["depth"]


                walls.append(
                    {
                        "floor": floor_name,
                        "room": room["name"],

                        "walls":[

                            {
                                "side":"north",
                                "x":x,
                                "y":y+d,
                                "length":w
                            },

                            {
                                "side":"south",
                                "x":x,
                                "y":y,
                                "length":w
                            },

                            {
                                "side":"east",
                                "x":x+w,
                                "y":y,
                                "length":d
                            },

                            {
                                "side":"west",
                                "x":x,
                                "y":y,
                                "length":d
                            }

                        ]
                    }
                )


        return {

            "engine":
                "wall_generator_v22.3",

            "status":
                "generated",

            "walls":
                walls
        }