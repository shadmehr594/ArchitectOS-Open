# ==========================================================
# ArchitectOS Chat Image Bridge v1
# Connects chat uploaded images to render runtime
# ==========================================================

from core.render.image_asset_bridge import ImageAssetBridge


class ChatImageBridge:


    VERSION = "1.0"


    def __init__(self):

        self.asset_bridge = ImageAssetBridge()

        print(
            "💬 CHAT IMAGE BRIDGE v1 ONLINE"
        )


    # ======================================================
    # HANDLE UPLOADED IMAGE
    # ======================================================

    def process_upload(
        self,
        project_id,
        image_path,
        preview=None
    ):

        asset = self.asset_bridge.register(
            project_id,
            image_path,
            preview=preview,
        )


        return {

            "type":
                "image_asset",

            "project_id":
                project_id,

            "asset":
                asset

        }