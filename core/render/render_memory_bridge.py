# ==========================================================
# ArchitectOS Render Memory Bridge v3.1
# Persistent Render Experience Layer
# Design Intelligence Extraction
# ==========================================================


import time
import json
import os
import uuid



class RenderMemoryBridge:


    VERSION = "3.1"



    def __init__(
        self,
        storage_path="core/memory/render_memory.json"
    ):


        self.storage_path = storage_path


        folder = os.path.dirname(
            self.storage_path
        )


        os.makedirs(
            folder,
            exist_ok=True
        )


        if not os.path.exists(
            self.storage_path
        ):

            with open(
                self.storage_path,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    [],
                    f,
                    indent=2,
                    ensure_ascii=False
                )


        print(
            "🧠 RENDER MEMORY BRIDGE v3.1 ONLINE"
        )



    # ======================================================
    # LOAD
    # ======================================================

    def _load(self):

        with open(
            self.storage_path,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)



    # ======================================================
    # SAVE
    # ======================================================

    def _save(
        self,
        data
    ):

        with open(
            self.storage_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False
            )



    # ======================================================
    # DESIGN EXTRACTION
    # ======================================================

    def extract_design(
        self,
        result
    ):


        prompt = result.get(
            "prompt",
            {}
        )


        if not isinstance(
            prompt,
            dict
        ):

            prompt = {}



        description = prompt.get(
            "description",
            ""
        )


        style = prompt.get(
            "style",
            "unknown"
        )


        building_type = prompt.get(
            "type",
            "building"
        )



        features = []



        feature_keywords = [

            "glass facade",

            "natural stone",

            "flat roof",

            "warm lighting",

            "minimalist",

            "garden",

            "pool",

            "parking",

            "green roof"

        ]



        text = description.lower()



        for feature in feature_keywords:


            if feature in text:

                features.append(
                    feature
                )



        return {


            "building_type":

                building_type,


            "style":

                style,


            "features":

                features,


            "source":

                "prompt_builder"


        }



    # ======================================================
    # STORE EXPERIENCE
    # ======================================================

    def store(
        self,
        result
    ):


        project_id = result.get(
            "project_id",
            "default"
        )



        design = result.get(
            "design"
        )



        if not design:

            design = self.extract_design(
                result
            )



        item = {


            "render_id":

                result.get(
                    "render_id",
                    "render_" +
                    uuid.uuid4()
                    .hex[:8]
                ),


            "type":

                "render_experience",


            "project_id":

                project_id,


            "engine":

                result.get(
                    "engine",
                    "flux"
                ),


            "workflow":

                result.get(
                    "workflow"
                ),


            "prompt":

                result.get(
                    "prompt"
                ),


            "design":

                design,


            "asset":

                result.get(
                    "asset",
                    {}
                ),


            "success":

                result.get(
                    "status"
                )
                ==
                "success",


            "created_at":

                time.time()

        }



        data = self._load()


        data.append(
            item
        )


        self._save(
            data
        )


        return item



    # ======================================================
    # PROJECT HISTORY
    # ======================================================

    def get_project_memory(
        self,
        project_id
    ):


        data = self._load()


        return [

            item

            for item in data

            if item.get(
                "project_id"
            )
            ==
            project_id

        ]



    # ======================================================
    # LATEST
    # ======================================================

    def latest(
        self,
        project_id
    ):


        items = self.get_project_memory(
            project_id
        )


        if not items:

            return None


        return items[-1]



    # ======================================================
    # SEARCH
    # ======================================================

    def search(
        self,
        keyword
    ):


        data = self._load()


        keyword = keyword.lower()


        return [

            item

            for item in data

            if keyword in str(item)
            .lower()

        ]