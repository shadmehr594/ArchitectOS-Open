# ==========================================================
# ArchitectOS Architectural Material Intelligence v1.2
#
# Architectural Intent
#        |
#        ↓
# Material Knowledge Enrichment
#        |
#        ↓
# Render Keywords + BIM Metadata
#        |
#        ↓
# Render / BIM / Prompt Intelligence
# ==========================================================


class ArchitecturalMaterialIntelligence:


    VERSION = "1.2"



    MATERIAL_KNOWLEDGE = {


        # ==================================================
        # STONE
        # ==================================================

        "سنگ":
        {
            "render": "natural stone facade",
            "bim":
            {
                "category": "stone",
                "application": "facade",
                "finish": "natural",
                "layer": "external_cladding"
            }
        },


        "تراورتن":
        {
            "render": "travertine stone facade",
            "bim":
            {
                "category": "stone",
                "application": "facade",
                "finish": "travertine natural",
                "layer": "external_cladding"
            }
        },


        "مرمر":
        {
            "render": "marble stone finish",
            "bim":
            {
                "category": "stone",
                "application": "interior_finish",
                "finish": "polished marble",
                "layer": "surface_finish"
            }
        },


        "گرانیت":
        {
            "render": "granite stone finish",
            "bim":
            {
                "category": "stone",
                "application": "floor_and_facade",
                "finish": "granite",
                "layer": "surface_finish"
            }
        },



        # ==================================================
        # WOOD
        # ==================================================

        "چوب":
        {
            "render": "natural wood cladding",
            "bim":
            {
                "category": "wood",
                "application": "wall_and_facade",
                "finish": "natural wood",
                "layer": "cladding"
            }
        },


        "ترموود":
        {
            "render": "thermowood cladding",
            "bim":
            {
                "category": "wood",
                "application": "facade",
                "finish": "thermal wood",
                "layer": "external_cladding"
            }
        },


        "پارکت":
        {
            "render": "oak parquet flooring",
            "bim":
            {
                "category": "wood",
                "application": "floor",
                "finish": "matte oak",
                "layer": "floor_finish"
            }
        },


        "بلوط":
        {
            "render": "oak wood flooring",
            "bim":
            {
                "category": "wood",
                "application": "floor",
                "finish": "oak",
                "layer": "floor_finish"
            }
        },



        # ==================================================
        # CONCRETE
        # ==================================================

        "بتن اکسپوز":
        {
            "render": "exposed architectural concrete",
            "bim":
            {
                "category": "concrete",
                "application": "wall_and_facade",
                "finish": "exposed",
                "layer": "structural_finish"
            }
        },


        "میکروسمنت":
        {
            "render": "microcement architectural finish",
            "bim":
            {
                "category": "cement",
                "application": "floor_and_wall",
                "finish": "smooth",
                "layer": "surface_finish"
            }
        },



        # ==================================================
        # CERAMIC / TILE
        # ==================================================

        "سرامیک":
        {
            "render": "porcelain tile flooring",
            "bim":
            {
                "category": "ceramic",
                "application": "floor",
                "finish": "tile",
                "layer": "floor_finish"
            }
        },


        "پرزسلان":
        {
            "render": "porcelain stoneware flooring",
            "bim":
            {
                "category": "ceramic",
                "application": "floor",
                "finish": "porcelain",
                "layer": "floor_finish"
            }
        },



        # ==================================================
        # METAL / GLASS
        # ==================================================

        "آلومینیوم":
        {
            "render": "aluminum facade panels",
            "bim":
            {
                "category": "metal",
                "application": "facade",
                "finish": "aluminum",
                "layer": "external_cladding"
            }
        },


        "شیشه":
        {
            "render": "glass facade",
            "bim":
            {
                "category": "glass",
                "application": "facade",
                "finish": "transparent",
                "layer": "curtain_wall"
            }
        },



        # ==================================================
        # BRICK
        # ==================================================

        "آجر":
        {
            "render": "brick facade",
            "bim":
            {
                "category": "brick",
                "application": "facade",
                "finish": "exposed brick",
                "layer": "external_wall_finish"
            }
        },


        "آجر نسوز":
        {
            "render": "fire brick facade",
            "bim":
            {
                "category": "brick",
                "application": "facade",
                "finish": "fire brick",
                "layer": "external_wall_finish"
            }
        }


    }



    def __init__(self):

        print(
            "🧱 ARCHITECTURAL MATERIAL INTELLIGENCE v1.2 ONLINE"
        )



    def enrich(
        self,
        architectural_intent,
        prompt=""
    ):


        if not isinstance(
            architectural_intent,
            dict
        ):

            architectural_intent = {}



        text = str(prompt).lower()



        materials = architectural_intent.get(
            "materials",
            []
        )


        metadata = architectural_intent.get(
            "material_metadata",
            []
        )


        if not isinstance(materials, list):
            materials = []


        if not isinstance(metadata, list):
            metadata = []



        detected = []



        for key, value in self.MATERIAL_KNOWLEDGE.items():


            if key in text:


                render_name = value["render"]


                if render_name not in materials:

                    materials.append(
                        render_name
                    )


                metadata.append(
                    {
                        "name": key,
                        **value["bim"]
                    }
                )


                detected.append(
                    render_name
                )



        # Remove duplicates

        unique_metadata = []

        for item in metadata:

            if item not in unique_metadata:

                unique_metadata.append(item)



        metadata = unique_metadata



        # ==================================================
        # STRATEGY
        # ==================================================


        has_stone = any(
            "stone" in x
            for x in materials
        )


        has_wood = any(
            "wood" in x
            or
            "oak" in x
            for x in materials
        )


        if has_stone and has_wood:


            architectural_intent["material_strategy"] = (
                "natural stone and timber combination"
            )


            architectural_intent["architectural_palette"] = [

                "warm natural materials",
                "modern organic architecture"

            ]



        elif any(
            "marble" in x
            for x in materials
        ):


            architectural_intent["material_strategy"] = (
                "luxury marble architectural language"
            )


            architectural_intent["architectural_palette"] = [

                "luxury stone textures",
                "premium modern architecture"

            ]



        architectural_intent["materials"] = materials


        architectural_intent["material_metadata"] = metadata



        print(
            "🧱 MATERIAL ENRICHMENT:",
            architectural_intent
        )


        return architectural_intent