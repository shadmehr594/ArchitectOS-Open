# ==========================================================
# ArchitectOS Render Memory v1
# Render Artifact Storage Layer
# ==========================================================


import time
import json
import os
import uuid



class RenderMemory:


    VERSION = "1.0"



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
                    indent=2
                )


        print(
            "🧠 RENDER MEMORY v1 ONLINE"
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
                indent=2
            )



    # ======================================================
    # STORE RENDER
    # ======================================================


    def store(
        self,
        project_id,
        render_result,
        design=None
    ):


        image = (
            render_result
            .get(
                "image",
                {}
            )
        )


        artifact = {


            "render_id":

                "render_" +
                uuid.uuid4().hex[:8],


            "project_id":

                project_id,


            "image":

                image,


            "design":

                design or {},


            "created_at":

                time.time()


        }


        data = self._load()


        data.append(
            artifact
        )


        self._save(
            data
        )


        return artifact



    # ======================================================
    # PROJECT HISTORY
    # ======================================================


    def history(
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
    # LAST RENDER
    # ======================================================


    def latest(
        self,
        project_id
    ):


        items = self.history(
            project_id
        )


        if not items:

            return None


        return items[-1]