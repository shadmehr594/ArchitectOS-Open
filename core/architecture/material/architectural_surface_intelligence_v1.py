class ArchitecturalSurfaceIntelligenceV1:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🎨 ARCHITECTURAL SURFACE INTELLIGENCE V1 ONLINE"
        )


    def generate(
        self,
        mesh_output
    ):


        result = {

            "version":
                self.VERSION,

            "surfaces":
                [],

            "materials":
                [],

            "finish_rules":
                []

        }


        # =================================
        # SURFACE GENERATION
        # =================================

        for mesh in mesh_output.get(
            "meshes",
            []
        ):


            result["surfaces"].append(

                {

                    "name":
                        mesh.get("name"),

                    "surface_type":
                        self.get_surface_type(
                            mesh.get("type")
                        )

                }

            )


        # =================================
        # MATERIAL RULES
        # =================================

        result["materials"] = [

            {

                "category":
                    "default",

                "material":
                    "architectural_standard"

            }

        ]


        # =================================
        # FINISH RULES
        # =================================

        result["finish_rules"].append(

            {

                "rule":
                    "every_surface_requires_material"

            }

        )


        return result



    def get_surface_type(
        self,
        mesh_type
    ):


        mapping = {


            "volume_mesh":
                "room_surface",


            "vertical_mesh":
                "vertical_surface"


        }


        return mapping.get(

            mesh_type,

            "generic_surface"

        )