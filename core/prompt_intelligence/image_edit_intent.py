# ==========================================================
# ArchitectOS Image Edit Intent Engine v1.1
# Geometry Preserving Image Edit Intelligence
# ==========================================================


class ImageEditIntent:


    VERSION = "1.1"



    def extract(
        self,
        design
    ):


        design = design or {}



        # ==================================================
        # RECOVER REAL USER TEXT
        # Priority:
        # 1 - prompt
        # 2 - text
        # 3 - fallback
        # ==================================================


        text = (

            design.get(
                "prompt",
                ""

            )

            or

            design.get(
                "text",
                ""

            )

        )



        text_lower = text.lower()



        intent = {


            "mode":
                "img2img",


            "preserve_geometry":
                True,


            "materials":
                [],


            "style":
                "",


            "remove_objects":
                [],


            "constraints":
                [

                    "preserve original geometry",

                    "preserve original camera",

                    "preserve original composition"

                ]

        }




        # ==================================================
        # MATERIAL DETECTION
        # ==================================================


        material_map = {


            "تراورتن":
                "travertine stone",


            "travertین":
                "travertine stone",


            "سنگ تراورتن":
                "travertine stone",


            "سنگ":
                "natural stone",


            "آجر":
                "brick facade",


            "چوب":
                "wood facade",


            "بتن":
                "exposed concrete"

        }



        for key, value in material_map.items():


            if key in text_lower:


                if value not in intent["materials"]:


                    intent["materials"].append(
                        value
                    )




        # ==================================================
        # STYLE DETECTION
        # ==================================================


        style_map = {


            "کلاسیک":
                "classical",


            "کلاسیکه":
                "classical",


            "مدرن":
                "modern",


            "مینیمال":
                "minimal",


            "نئوکلاسیک":
                "neoclassical"

        }



        for key,value in style_map.items():


            if key in text_lower:


                intent["style"] = value





        # ==================================================
        # PRESERVE GEOMETRY INTENT
        # ==================================================


        geometry_keywords = [

            "بدون تغییر فرم",

            "بدون تغییر شکل",

            "حفظ فرم",

            "حفظ ساختار",

            "تغییر نده",

            "preserve geometry"

        ]



        for word in geometry_keywords:


            if word in text_lower:


                intent["preserve_geometry"] = True

                break





        # ==================================================
        # REMOVE OBJECTS
        # ==================================================


        cleanup_words = {


            "بالابر":
                "construction lift",


            "داربست":
                "scaffolding",


            "جرثقیل":
                "construction equipment"

        }



        for key,value in cleanup_words.items():


            if key in text_lower:


                intent["remove_objects"].append(
                    value
                )




        print(
            "🧠 IMAGE EDIT INTENT RECOVERY:",
            intent
        )



        return intent