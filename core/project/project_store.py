# ==========================================================
# ArchitectOS Project Store v1
# Persistent Project Storage
# ==========================================================

import os
import json


class ProjectStore:

    VERSION = "1.0"


    def __init__(self):

        self.root = "projects"

        os.makedirs(
            self.root,
            exist_ok=True
        )

        print(
            "📁 PROJECT STORE v1 ONLINE"
        )



    def save(
        self,
        project_id,
        filename,
        data
    ):

        folder = os.path.join(
            self.root,
            project_id
        )

        os.makedirs(
            folder,
            exist_ok=True
        )


        path = os.path.join(
            folder,
            filename
        )


        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=4,
                default=str
            )


        return path



    def load(
        self,
        project_id,
        filename
    ):

        path = os.path.join(
            self.root,
            project_id,
            filename
        )


        if not os.path.exists(path):

            return None


        with open(
            path,
            encoding="utf-8"
        ) as f:

            return json.load(f)