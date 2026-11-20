class ArchitecturalMeshAdapterV1:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🧩 ARCHITECTURAL MESH ADAPTER V1 ONLINE"
        )


    def generate(
        self,
        geometry_output
    ):


        result = {

            "version":
                self.VERSION,

            "meshes":
                [],

            "materials":
                [],

            "topology":
                []

        }


        # ==============================
        # SPACE MESH
        # ==============================

        for space in geometry_output.get(
            "spaces",
            []
        ):

            result["meshes"].append(

                {

                    "name":
                        space.get("name"),

                    "type":
                        "volume_mesh",

                    "source":
                        "room_volume",

                    "height":
                        space.get(
                            "height",
                            3.2
                        )

                }

            )


        # ==============================
        # VERTICAL MESH
        # ==============================

        for element in geometry_output.get(
            "vertical_geometry",
            []
        ):

            result["meshes"].append(

                {

                    "name":
                        element.get("name"),

                    "type":
                        "vertical_mesh",

                    "source":
                        element.get("type")

                }

            )


        # ==============================
        # TOPOLOGY CONTRACT
        # ==============================

        result["topology"].append(

            {

                "rule":
                    "mesh_requires_closed_volume"

            }

        )


        return result