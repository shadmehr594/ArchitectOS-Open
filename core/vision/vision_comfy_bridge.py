# ==========================================================
# ArchitectOS Vision Comfy Bridge v3
# Vision -> Facade Prompt -> Comfy Img2Img
# Original Geometry Preservation
# ==========================================================


from core.vision.facade_prompt_builder import facade_prompt_builder
from skills.comfyui.comfy_runtime import ComfyRuntime



class VisionComfyBridge:


    def __init__(self):

        self.comfy = ComfyRuntime()

        print(
            "🔗 Vision Comfy Bridge v3 ACTIVE"
        )



    def redesign_facade(
        self,
        vision_data
    ):


        # ==============================================
        # BUILD ARCHITECTURAL PROMPT
        # ==============================================

        prompt_data = facade_prompt_builder.build(

            vision_data.get(
                "vision_result",
                {}
            ),

            vision_data.get(
                "facade_result",
                {}
            )

        )



        # ==============================================
        # ORIGINAL IMAGE SOURCE
        # ==============================================

        source_image = (

            vision_data
            .get(
                "vision_result",
                {}
            )
            .get(
                "image",
                None
            )

        )



        print(
            "🏠 ORIGINAL IMAGE:",
            source_image
        )



        # ==============================================
        # SEND TO COMFY IMG2IMG
        # ==============================================

        result = self.comfy.generate(

            prompt_data["prompt"],

            "edit",

            source_image

        )



        return {


            "prompt":

                prompt_data,


            "source_image":

                source_image,


            "comfy_result":

                result

        }



vision_comfy_bridge = VisionComfyBridge()