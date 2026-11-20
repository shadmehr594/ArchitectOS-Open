class BIMElementMapper:

    def __init__(self):
        print("🧱 BIM Element Mapper v66.2 ACTIVE")


    def map(self, structure_result):

        structure = structure_result.get(
            "building_structure",
            {}
        )


        floors = structure.get(
            "floors",
            []
        )


        walls = structure.get(
            "walls",
            []
        )


        openings = structure.get(
            "openings",
            []
        )


        elements = {

            "walls": [],

            "floors": [],

            "openings": []

        }


        for wall in walls:

            elements["walls"].append({

                "id":
                    wall.get("id"),

                "category":
                    "Wall",

                "type":
                    wall.get(
                        "type",
                        "unknown"
                    ),

                "material":
                    wall.get(
                        "material",
                        "unknown"
                    )

            })


        for floor in floors:

            elements["floors"].append({

                "level":
                    floor.get(
                        "level"
                    ),

                "height":
                    floor.get(
                        "height"
                    ),

                "category":
                    "Floor"

            })


        for opening in openings:

            elements["openings"].append({

                "type":
                    opening.get(
                        "type",
                        "unknown"
                    ),

                "count":
                    opening.get(
                        "count",
                        0
                    ),

                "category":
                    "Opening"

            })


        return elements