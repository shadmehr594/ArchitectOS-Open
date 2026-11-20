class ArchitecturalMaterialIntelligenceV1:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🧱 ARCHITECTURAL MATERIAL INTELLIGENCE V1 ONLINE"
        )


    def generate(
        self,
        surface_output
    ):


        result = {

            "version":
                self.VERSION,

            "materials":
                [],

            "material_rules":
                []

        }


        # ==============================
        # MATERIAL MAPPING
        # ==============================

        for surface in surface_output.get(
            "surfaces",
            []
        ):


            surface_type = surface.get(
                "surface_type"
            )


            result["materials"].append(

                {

                    "surface":
                        surface.get(
                            "name"
                        ),

                    "material":
                        self.get_material(
                            surface_type
                        )

                }

            )


        # ==============================
        # RULES
        # ==============================

        result["material_rules"] = [

            "every_surface_has_material",

            "material_depends_on_surface_type",

            "architecture_controls_finish"

        ]


        return result



    def get_material(
        self,
        surface_type
    ):


        mapping = {


            "room_surface":
                "architectural_wall_finish",


            "vertical_surface":
                "structural_finish",


            "opening_surface":
                "glass_system"


        }


        return mapping.get(

            surface_type,

            "default_material"

        )