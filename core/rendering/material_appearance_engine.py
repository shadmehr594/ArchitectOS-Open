class MaterialAppearanceEngine:


    def __init__(self):

        print(
            "🎨 Material Appearance Engine v28.1 ACTIVE"
        )


        self.library = {


            "reinforced_concrete":

            {

                "category":
                "structural",

                "appearance":
                "concrete_gray",

                "roughness":
                0.9

            },


            "brick":

            {

                "category":
                "masonry",

                "appearance":
                "red_clay_brick",

                "roughness":
                0.85,

                "pattern":
                "running_bond"

            },


            "stone":

            {

                "category":
                "masonry",

                "appearance":
                "natural_stone",

                "roughness":
                0.8

            },


            "glass":

            {

                "category":
                "envelope",

                "appearance":
                "transparent",

                "roughness":
                0.1

            },


            "wood":

            {

                "category":
                "finish",

                "appearance":
                "natural_wood",

                "roughness":
                0.6

            },


            "metal":

            {

                "category":
                "finish",

                "appearance":
                "metallic",

                "roughness":
                0.3

            },


            "green_roof":

            {

                "category":
                "landscape",

                "appearance":
                "vegetation"

            },


            "paint":

            {

                "category":
                "finish",

                "appearance":
                "colored_surface"

            }

        }



    def apply(
        self,
        scene,
        material_map=None
    ):


        material_map = material_map or {}


        objects = (

            scene
            .get(
                "scene",
                {}
            )
            .get(
                "objects",
                []
            )

        )


        applied = []



        for obj in objects:


            obj_type = obj.get(
                "type"
            )


            material = material_map.get(

                obj_type,

                self._default_material(
                    obj_type
                )

            )


            data = self.library.get(

                material,

                self.library["paint"]

            )


            applied.append(

                {

                    "object":
                    obj.get(
                        "id",
                        obj_type
                    ),


                    "type":
                    obj_type,


                    "material":
                    material,


                    "appearance":
                    data.get(
                        "appearance"
                    ),


                    "properties":
                    data

                }

            )



        return {


            "engine":
            "material_appearance_v28.1",


            "status":
            "applied",


            "materials":
            applied,


            "library_size":
            len(
                self.library
            ),


            "render_ready":
            True

        }



    def _default_material(
        self,
        obj_type
    ):


        if obj_type == "wall_mesh":

            return "reinforced_concrete"


        if obj_type == "window_void":

            return "glass"


        if obj_type == "space_volume":

            return "paint"


        if obj_type == "roof_surface":

            return "green_roof"


        return "paint"