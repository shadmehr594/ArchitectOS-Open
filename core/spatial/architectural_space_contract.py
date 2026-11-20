"""
ArchitectOS Architectural Space Contract v1.0

Unified architectural representation for:
- Rooms
- Courtyards
- Circulation
- External spaces

Bridge:
Planner
    ↓
Architectural Intelligence
    ↓
Spatial Engine
    ↓
Geometry
"""


class ArchitecturalSpaceContract:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"🏛️ Architectural Space Contract v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # CREATE SPACE NODE
    # ==================================================

    def create_space(
        self,
        space_id,
        space_type,
        geometry=None,
        requirements=None,
        adjacency=None
    ):


        return {

            "id":
                space_id,


            "type":
                space_type,


            "geometry":
                geometry
                or {},


            "requirements":
                requirements
                or {},


            "adjacency":
                adjacency
                or {}

        }



    # ==================================================
    # COURTYARD CONTRACT
    # ==================================================

    def from_courtyard(
        self,
        courtyard
    ):


        return self.create_space(

            space_id="courtyard_001",

            space_type="courtyard",

            geometry={

                "polygon":
                    courtyard.get(
                        "polygon",
                        []
                    ),

                "area":
                    courtyard.get(
                        "area",
                        0
                    )

            },


            requirements={

                "natural_light":
                    True,


                "ventilation":
                    True,


                "open_to_sky":
                    True

            },


            adjacency={

                "preferred":

                    [

                        "circulation",

                        "lobby",

                        "living"

                    ],


                "avoid":

                    [

                        "storage"

                    ]

            }

        )



    # ==================================================
    # ROOM CONTRACT
    # ==================================================

    def from_room(
        self,
        room
    ):


        return self.create_space(

            space_id=
                room.get(
                    "id"
                ),


            space_type=
                room.get(
                    "type",
                    "room"
                ),


            geometry=room,


            requirements={

                "area":
                    room.get(
                        "area"
                    )

            }

        )