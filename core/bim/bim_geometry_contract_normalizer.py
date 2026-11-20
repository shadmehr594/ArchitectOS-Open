from copy import deepcopy


class BIMGeometryContractNormalizer:
    """
    BIM Geometry Contract Normalizer v1.0

    Converts external geometry contracts
    (Design / CAD / adapters)
    into internal StructureEngine geometry format.
    """

    VERSION = "1.0"


    def __init__(self):

        print(
            "📐 BIM Geometry Contract Normalizer v1.0 ACTIVE"
        )


    def normalize(self, geometry):

        if not geometry:
            return self._fallback()


        rooms = []


        print("\n====== NORMALIZER INPUT ROOMS ======")

        for r in geometry.get("rooms", [])[:10]:
            print(
                r.get("id"),
                r.get("level"),
                r
            )


        for room in geometry.get(
            "rooms",
            []
        ):

            # Already internal format
            if (
                "x" in room
                and
                "y" in room
            ):

                room.setdefault(
                    "w",
                    5
                )

                room.setdefault(
                    "h",
                    5
                )

                room.setdefault(
                    "height",
                    3.2
                )

                rooms.append(
                    room
                )

                continue


            # External geometry contract
            geo = room.get(
                "geometry",
                {}
            )


            rooms.append(

                {
                    "id":
                    room.get(
                        "id",
                        "room"
                    ),

                    "type":
                    room.get(
                        "type",
                        "space"
                    ),

                    "level":
                    room.get(
                        "level"
                    ),

                    "x":
                    geo.get(
                        "x",
                        0
                    ),

                    "y":
                    geo.get(
                        "y",
                        0
                    ),

                    "w":
                    geo.get(
                        "width",
                        geo.get(
                            "w",
                            5
                        )
                    ),

                    "h":
                    geo.get(
                        "height",
                        geo.get(
                            "h",
                            5
                        )
                    ),

                    "height":
                    geo.get(
                        "room_height",
                        3.2
                    )
                }

            )

        print("\n====== NORMALIZER OUTPUT ROOMS ======")

        for r in rooms[:10]:
            print(
                r.get("id"),
                r.get("level"),
                r
            )


        result = deepcopy(geometry)
        result.update({
            "rooms": rooms,
            "floors": geometry.get("floors", []),
            "levels": geometry.get("levels", []),
            "walls": geometry.get("walls", []),
            "doors": geometry.get("doors", []),
            "windows": geometry.get("windows", []),
        })
        return result



    def _fallback(self):

        return {

            "rooms":[

                {
                    "x":0,
                    "y":0,
                    "w":5,
                    "h":5,
                    "height":3.2
                }

            ],

            "floors":[],

            "levels":[],

            "walls":[],

            "doors":[],

            "windows":[]

        }
