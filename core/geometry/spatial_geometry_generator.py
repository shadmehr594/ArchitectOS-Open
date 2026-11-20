"""
ArchitectOS Spatial Geometry Generator v1.0

Converts room layout into spatial polygons.
"""


class SpatialGeometryGenerator:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"📐 Spatial Geometry Generator v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # ROOM RECTANGLE
    # ==================================================

    def create_rectangle(
        self,
        x,
        y,
        width,
        depth
    ):


        return [

            [x, y],

            [x + width, y],

            [x + width, y + depth],

            [x, y + depth]

        ]



    # ==================================================
    # GENERATE ROOM GEOMETRY
    # ==================================================

    def generate(
        self,
        room_layout,
        unit
    ):


        rooms = []

        x_offset = 0



        for room in room_layout.get(
            "rooms",
            []
        ):


            room_type = room.get(
                "type"
            )


            width = 4

            depth = 5



            polygon = self.create_rectangle(

                x_offset,

                0,

                width,

                depth

            )



            rooms.append(

                {

                    "type":
                        room_type,


                    "polygon":
                        polygon,


                    "area":
                        width * depth,


                    "adjacent":

                    [

                        "corridor"

                    ]

                }

            )



            x_offset += width



        result = {


            "unit":

                unit.get(
                    "id"
                ),


            "rooms":

                rooms

        }



        # ==================================================
        # DEBUG
        # ==================================================

        print(
            "\n===== SPATIAL GEOMETRY OUTPUT DEBUG ====="
        )

        print(
            "TYPE:",
            type(result)
        )


        if isinstance(result, dict):

            print(
                "KEYS:",
                list(result.keys())
            )


            print(
                "ROOM COUNT:",
                len(
                    result.get(
                        "rooms",
                        []
                    )
                )
            )


            if result.get("rooms"):

                print(
                    "ROOM SAMPLE:",
                    result["rooms"][:1]
                )


        print(
            "========================================\n"
        )



        return result