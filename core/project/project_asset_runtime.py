# ==========================================================
# ArchitectOS Project Asset Runtime v1
# Project + Asset Integration Layer
# ==========================================================


from core.project.project_runtime import ProjectRuntime
from core.asset.asset_manager import AssetManager

import time



class ProjectAssetRuntime:


    VERSION = "1.0"



    def __init__(self):

        self.project_runtime = ProjectRuntime()

        self.asset_manager = AssetManager()


        print(
            "🔗 PROJECT ASSET RUNTIME v1 ONLINE"
        )



    # ======================================================
    # CREATE DESIGN PROJECT
    # ======================================================


    def create_design_project(
        self,
        name,
        design_data
    ):


        project_result = (
            self.project_runtime
            .create_design_project(
                name,
                design_data
            )
        )


        project_id = (
            project_result["project_id"]
        )



        design_asset = (
            self.asset_manager.register(
                project_id,
                "design",
                "design.json",
                {
                    "source":
                        "architectos_runtime",

                    "created":
                        time.time(),

                    "type":
                        design_data.get(
                            "type",
                            "unknown"
                        )
                }
            )
        )


        return {

            "project":
                project_result["project"],

            "design_asset":
                design_asset,

            "project_id":
                project_id

        }



    # ======================================================
    # ADD RENDER ASSET
    # ======================================================


    def add_render(
        self,
        project_id,
        filename,
        engine="flux"
    ):


        return (
            self.asset_manager
            .create_render_asset(
                project_id,
                filename,
                engine
            )
        )