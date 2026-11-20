# ==========================================================
# ArchitectOS Render Experience Memory v1
# Successful Render Pattern Extraction Layer
# ==========================================================


import os
import json
import time



class RenderExperienceMemory:


    VERSION = "1.0"



    def __init__(
        self,
        storage_path="core/memory/render_memory.json"
    ):


        self.storage_path = storage_path


        print(
            "🧠 RENDER EXPERIENCE MEMORY v1 ONLINE"
        )



    # ======================================================
    # LOAD RENDER MEMORY
    # ======================================================


    def _load(self):


        if not os.path.exists(
            self.storage_path
        ):

            return []


        try:

            with open(
                self.storage_path,
                "r",
                encoding="utf-8"
            ) as f:

                return json.load(f)


        except Exception:


            return []



    # ======================================================
    # SUCCESSFUL RENDER FILTER
    # ======================================================


    def successful_renders(
        self
    ):


        data = self._load()


        return [

            item

            for item in data

            if item.get(
                "success",
                False
            )

        ]



    # ======================================================
    # EXTRACT EXPERIENCE
    # ======================================================


    def get_context(
        self,
        limit=5
    ):


        renders = (
            self.successful_renders()
        )


        renders = renders[-limit:]



        styles = []

        features = []

        materials = []

        patterns = []



        for item in renders:


            design = item.get(
                "design",
                {}
            )


            prompt = item.get(
                "prompt",
                ""
            )



            style = design.get(
                "style"
            )


            if style and style not in styles:

                styles.append(
                    style
                )



            for feature in design.get(
                "features",
                []
            ):


                if feature not in features:

                    features.append(
                        feature
                    )



            text = (
                str(prompt)
                .lower()
            )


            if "glass" in text:

                materials.append(
                    "glass facade"
                )


            if "stone" in text:

                materials.append(
                    "natural stone"
                )


            if "minimal" in text:

                patterns.append(
                    "minimalist architecture"
                )



            if "flat roof" in text:

                patterns.append(
                    "flat roof design"
                )



        return {


            "successful_render_experience": {


                "styles":
                    styles,


                "features":
                    features,


                "materials":
                    list(
                        set(materials)
                    ),


                "patterns":
                    list(
                        set(patterns)
                    ),


                "source_count":
                    len(renders),


                "timestamp":
                    time.time()


            }


        }