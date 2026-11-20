# ==========================================================
# ArchitectOS Asset Store v1
# Project Asset Persistence Layer
# ==========================================================


import os
import json
import time



class AssetStore:


    VERSION = "1.0"



    def __init__(self):

        self.root = "projects"


        print(
            "🗂️ ASSET STORE v1 ONLINE"
        )



    # ======================================================
    # SAVE ASSET
    # ======================================================


    def save_asset(
        self,
        project_id,
        asset_type,
        filename,
        metadata=None
    ):


        folder = os.path.join(
            self.root,
            project_id,
            "assets",
            asset_type
        )


        os.makedirs(
            folder,
            exist_ok=True
        )


        meta = {

            "project_id":
                project_id,

            "type":
                asset_type,

            "filename":
                filename,

            "created_at":
                time.time(),

            "metadata":
                metadata or {}

        }



        meta_path = os.path.join(
            folder,
            filename + ".json"
        )


        with open(
            meta_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                meta,
                f,
                ensure_ascii=False,
                indent=4
            )


        return meta



    # ======================================================
    # LOAD ASSET
    # ======================================================


    def load_asset(
        self,
        project_id,
        asset_type,
        filename
    ):


        path = os.path.join(
            self.root,
            project_id,
            "assets",
            asset_type,
            filename + ".json"
        )


        if not os.path.exists(path):

            return None



        with open(
            path,
            encoding="utf-8"
        ) as f:

            return json.load(f)