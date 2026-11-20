class ArchitecturalDocumentationEngine:


    def __init__(self):

        print(
            "📐 Architectural Documentation Engine v23.3 ACTIVE"
        )


    def generate(
        self,
        bim_metadata,
        project_data=None
    ):


        metadata = bim_metadata.get(
            "metadata",
            {}
        )


        documentation = {

            "room_schedule": [],

            "wall_schedule": [],

            "opening_schedule": [],

            "project_summary": {}

        }


        # ----------------------
        # Room Schedule
        # ----------------------

        for room in metadata.get(
            "rooms",
            []
        ):

            documentation["room_schedule"].append(

                {
                    "name":
                        room.get("name"),

                    "category":
                        room.get("category"),

                    "usage":
                        room.get("usage")

                }

            )


        # ----------------------
        # Wall Schedule
        # ----------------------

        for wall in metadata.get(
            "walls",
            []
        ):

            documentation["wall_schedule"].append(

                {
                    "floor":
                        wall.get("floor"),

                    "material":
                        wall.get("material"),

                    "thickness":
                        wall.get("thickness"),

                    "fire_rating":
                        wall.get("fire_rating")

                }

            )


        # ----------------------
        # Opening Schedule
        # ----------------------

        for opening in metadata.get(
            "openings",
            []
        ):

            documentation["opening_schedule"].append(

                {
                    "type":
                        opening.get("type"),

                    "material":
                        opening.get("material"),

                    "thermal_rating":
                        opening.get("thermal_rating")

                }

            )


        # ----------------------
        # Summary
        # ----------------------

        documentation["project_summary"] = {

            "rooms":
                len(
                    documentation["room_schedule"]
                ),

            "walls":
                len(
                    documentation["wall_schedule"]
                ),

            "openings":
                len(
                    documentation["opening_schedule"]
                )

        }


        return {

            "engine":
                "architectural_documentation_v23.3",

            "status":
                "generated",

            "documentation":
                documentation

        }