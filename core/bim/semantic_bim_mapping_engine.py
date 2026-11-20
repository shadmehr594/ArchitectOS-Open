"""
ArchitectOS Semantic BIM Mapping Engine v1.0

Maps architectural elements into BIM semantic objects.
"""


class SemanticBIMMappingEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🧩 Semantic BIM Mapping Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # SPACE MAPPING
    # ==================================================

    def map_space(
        self,
        room
    ):


        return {


            "ifc_type":
                "IfcSpace",


            "name":
                room.get(
                    "type"
                ),


            "zone":
                room.get(
                    "zone",
                    "unknown"
                ),


            "geometry":
                room.get(
                    "polygon"
                )

        }



    # ==================================================
    # WALL MAPPING
    # ==================================================

    def map_wall(
        self,
        wall
    ):


        return {


            "ifc_type":
                "IfcWall",


            "wall_type":
                wall.get(
                    "type"
                ),


            "thickness":
                wall.get(
                    "thickness"
                ),


            "boundary":
                wall.get(
                    "edge"
                )

        }



    # ==================================================
    # OPENING MAPPING
    # ==================================================

    def map_opening(
        self,
        opening
    ):


        opening_type = opening.get(
            "type"
        )


        if opening_type == "door":

            ifc_type = "IfcDoor"


        elif opening_type == "window":

            ifc_type = "IfcWindow"


        else:

            ifc_type = "IfcBuildingElementProxy"



        return {


            "ifc_type":
                ifc_type,


            "room":
                opening.get(
                    "room"
                ),


            "source":
                opening.get(
                    "source"
                )

        }



    # ==================================================
    # GENERATE
    # ==================================================

    def generate(
        self,
        spaces,
        walls,
        openings
    ):

        print("\n===== SEMANTIC BIM ENGINE INPUT =====")

        print("SPACES TYPE:", type(spaces))

        if isinstance(spaces, list):
            print("SPACES COUNT:", len(spaces))
            print("SPACE SAMPLE:", spaces[:1])

        print("WALLS TYPE:", type(walls))

        if isinstance(walls, list):
            print("WALL COUNT:", len(walls))
            print("WALL SAMPLE:", walls[:1])

        print("OPENINGS TYPE:", type(openings))

        if isinstance(openings, list):
            print("OPENINGS COUNT:", len(openings))
            print("OPENING SAMPLE:", openings[:1])

        print("=====================================\n")


        elements = []



        for room in spaces:

            elements.append(

                self.map_space(
                    room
                )

            )



        for wall in walls:

            elements.append(

                self.map_wall(
                    wall
                )

            )



        for opening in openings:

            elements.append(

                self.map_opening(
                    opening
                )

            )



        return {


            "elements":
                elements

        }