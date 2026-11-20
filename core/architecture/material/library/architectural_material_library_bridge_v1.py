class ArchitecturalMaterialLibraryBridgeV1:


    VERSION = "1.0"


    def __init__(self):

        print(
            "📚 ARCHITECTURAL MATERIAL LIBRARY BRIDGE V1 ONLINE"
        )


        self.library = {

            "brick":

                {

                    "id":
                        "facade_brick_modern_001",

                    "category":
                        "facade",

                    "finish":
                        "rough",

                    "style":
                        "modern"

                },


            "glass":

                {

                    "id":
                        "glass_system_modern_001",

                    "category":
                        "opening",

                    "finish":
                        "transparent",

                    "style":
                        "modern"

                },


            "concrete":

                {

                    "id":
                        "concrete_exposed_001",

                    "category":
                        "structure",

                    "finish":
                        "raw",

                    "style":
                        "industrial"

                }

        }



    def resolve(
        self,
        material_output
    ):


        result = {

            "version":
                self.VERSION,

            "assets":
                [],

            "library":
                "architectural_material_library"

        }



        for item in material_output.get(
            "materials",
            []
        ):


            material_name = self.detect_material(
                item.get(
                    "material"
                )
            )


            asset = self.library.get(

                material_name,

                {

                    "id":
                        "default_material_001",

                    "category":
                        "generic",

                    "finish":
                        "standard",

                    "style":
                        "neutral"

                }

            )


            result["assets"].append(

                {

                    "surface":
                        item.get(
                            "surface"
                        ),

                    "asset":
                        asset

                }

            )


        return result



    def detect_material(
        self,
        material
    ):


        if "wall" in material:

            return "brick"


        if "glass" in material:

            return "glass"


        if "struct" in material:

            return "concrete"


        return "brick"