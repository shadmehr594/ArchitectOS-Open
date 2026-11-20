# ==========================================================
# ArchitectOS Image Input Manager v1
# Chat Image -> Render Asset
# ==========================================================


import os
import time
import uuid
import shutil



class ImageInputManager:


    VERSION = "1.0"



    def __init__(
        self,
        base_path="assets/images"
    ):

        self.base_path = base_path

        os.makedirs(
            self.base_path,
            exist_ok=True
        )

        print(
            "🖼️ IMAGE INPUT MANAGER v1 ONLINE"
        )



    def register(
        self,
        project_id,
        image_path
    ):


        filename = os.path.basename(
            image_path
        )


        asset_id = (
            "image_"
            +
            uuid.uuid4().hex[:8]
        )


        target = os.path.join(
            self.base_path,
            asset_id + "_" + filename
        )


        shutil.copy(
            image_path,
            target
        )


        return {

            "asset_id":
                asset_id,

            "project_id":
                project_id,

            "path":
                target,

            "filename":
                filename,

            "created_at":
                time.time()

        }