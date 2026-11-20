# ==========================================================
# ArchitectOS Asset Manager v1
# Asset Intelligence Layer
# ==========================================================


from core.asset.asset_store import AssetStore

import uuid
import time



class AssetManager:


    VERSION = "1.0"



    def __init__(self):

        self.store = AssetStore()


        print(
            "🚀 ASSET MANAGER v1 ONLINE"
        )



    # ======================================================
    # REGISTER ASSET
    # ======================================================


    def register(
        self,
        project_id,
        asset_type,
        filename,
        metadata=None
    ):


        asset_id = (
            "asset_"
            + str(uuid.uuid4())[:8]
        )


        data = {

            "asset_id":
                asset_id,

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


        self.store.save_asset(
            project_id,
            asset_type,
            filename,
            data
        )


        return data



    # ======================================================
    # GET ASSET
    # ======================================================


    def get(
        self,
        project_id,
        asset_type,
        filename
    ):


        return self.store.load_asset(
            project_id,
            asset_type,
            filename
        )



    # ======================================================
    # CREATE RENDER ASSET
    # ======================================================


    def create_render_asset(
        self,
        project_id,
        filename,
        engine="flux"
    ):


        return self.register(
            project_id,
            "renders",
            filename,
            {
                "engine": engine,
                "status": "ready"
            }
        )