# ==========================================================
# ArchitectOS Image Tool v3.2
# Image Gateway
#
# Responsibility:
# - Receive image requests
# - Register image asset
# - Build render state
# - Delegate to RenderRuntime
#
# RenderRuntime owns:
# - Intent
# - Prompt
# - Workflow
# - Execution
# - Result Bridge
# ==========================================================


from core.tools.base import BaseTool

from core.render.render_runtime import RenderRuntime
from core.render.image_asset_bridge import ImageAssetBridge



class ImageTool(BaseTool):


    name = "image"


    VERSION = "3.2"



    def __init__(self):


        self.runtime = RenderRuntime()

        self.asset_bridge = ImageAssetBridge()


        print(
            "🖼️ IMAGE TOOL v3.2 ONLINE"
        )



    # ======================================================
    # EXECUTE
    # ======================================================


    def execute(
        self,
        state,
        context=None
    ):


        state = state or {}

        context = context or {}



        prompt = (

            state.get(
                "prompt",
                ""
            )

            or

            state.get(
                "text",
                ""
            )

        )



        project_id = state.get(
            "project_id",
            "default"
        )



        mode = state.get(
            "mode",
            "text2img"
        )


        if mode == "generate":

            mode = "text2img"



        engine = state.get(
            "engine",
            "flux"
        )



        image = state.get(
            "image"
        )



        image_asset = None



        # ==================================================
        # IMAGE ASSET REGISTER
        # ==================================================


        if image:


            path = image.get(
                "path"
            )



            if path:


                image_asset = self.asset_bridge.register(

                    project_id,

                    path

                )


                image_asset = self.asset_bridge.prepare_asset(

                    image_asset

                )


            else:


                image_asset = {

                    "filename":
                        image.get(
                            "filename"
                        )

                }



        # ==================================================
        # BUILD DESIGN STATE
        # ==================================================


        design_context = {


            "prompt":

                prompt,


            "mode":

                mode,


            "engine":

                engine,


            "architectural_intent":

                state.get(
                    "architectural_intent",
                    {}
                ),



            "previous_design":

                context.get(
                    "previous_design",
                    {}
                ),



            "image_asset":

                image_asset



        }



        print(
            "🧠 IMAGE TOOL STATE:",
            design_context
        )



        # ==================================================
        # DELEGATE TO RENDER RUNTIME
        # ==================================================


        return self.runtime.render(

            project_id=

                project_id,


            design=

                design_context,


            engine=

                engine,


            image_asset=

                image_asset

        )