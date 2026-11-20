# ==========================================================
# ArchitectOS Render Result Bridge v1
# ComfyUI Output -> Chat/UI Response
# ==========================================================


import os
import time


class RenderResultBridge:


    VERSION = "v1"


    def __init__(self):

        print(
            "🖼️ RENDER RESULT BRIDGE v1 ONLINE"
        )


        self.output_dir = (
            "C:/ComfyUI-Zluda/output"
        )



    # ======================================================
    # RESOLVE
    # ======================================================

    def resolve(
        self,
        render_result
    ):


        try:

            execution = (
                render_result
                .get("execution", {})
            )


            inner = (
                execution
                .get("execution", {})
            )


            response = (
                inner
                .get("response", {})
            )


            prompt_id = (
                response
                .get("prompt_id")
            )


            if not prompt_id:


                return {

                    "status":
                        "pending",

                    "render":
                        render_result

                }



            from core.render.comfy_http_runtime import ComfyHTTPRuntime


            comfy = ComfyHTTPRuntime()


            history = comfy.history(
                prompt_id
            )


            data = (
                history
                .get(prompt_id, {})
            )


            outputs = (
                data
                .get("outputs", {})
            )


            for node in outputs.values():


                images = node.get(
                    "images",
                    []
                )


                if images:


                    image = images[0]


                    filename = image.get(
                        "filename"
                    )


                    return {


                        "status":
                            "success",


                        "prompt_id":
                            prompt_id,


                        "image": {


                            "filename":
                                filename,


                            "path":
                                os.path.join(

                                    self.output_dir,

                                    filename

                                ),


                            "type":
                                image.get(
                                    "type"
                                )

                        },


                        "created_at":
                            time.time()


                    }



            return {


                "status":
                    "completed_no_image",


                "prompt_id":
                    prompt_id

            }



        except Exception as e:


            return {


                "status":
                    "error",


                "error":
                    str(e)

            }