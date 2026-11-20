"""
ArchitectOS Wall Generator v1.0

Creates walls from room polygons.
"""


class WallGenerator:


    VERSION = "1.0"



    def __init__(
        self,
        wall_thickness=0.2
    ):


        self.wall_thickness = wall_thickness


        print(
            f"🧱 Wall Generator v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # EDGE KEY
    # ==================================================

    def edge_key(
        self,
        p1,
        p2
    ):


        return tuple(
            sorted(
                [

                    tuple(p1),

                    tuple(p2)

                ]
            )
        )



    # ==================================================
    # GENERATE
    # ==================================================

    def generate(
        self,
        geometry
    ):


        edge_map = {}



        rooms = geometry.get(
            "rooms",
            []
        )



        for room in rooms:


            polygon = room.get(
                "polygon",
                []
            )


            for i in range(
                len(polygon)
            ):


                p1 = polygon[i]


                p2 = polygon[

                    (i + 1)

                    %

                    len(polygon)

                ]



                key = self.edge_key(

                    p1,

                    p2

                )



                if key not in edge_map:

                    edge_map[key] = []


                edge_map[key].append(

                    room.get(
                        "type"
                    )

                )



        walls = []



        for edge, adjacent in edge_map.items():


            if len(adjacent) > 1:


                wall_type = "interior"


            else:


                wall_type = "exterior"



            walls.append({

                "type":
                    wall_type,


                "edge":
                    list(edge),


                "adjacent_rooms":
                    adjacent,


                "thickness":
                    self.wall_thickness

            })



        return {


            "walls":
                walls

        }