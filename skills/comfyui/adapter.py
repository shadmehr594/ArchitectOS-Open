from skills.comfyui.client import send_workflow
from skills.comfyui.workflow_engine import engine
from skills.comfyui.image_fetcher import get_image


class ComfyClientAdapter:


    def __init__(self):

        self.name = "ArchitectOS_Comfy_Adapter_v1"



    def generate(
        self,
        prompt
    ):


        # ==========================
        # WORKFLOW SELECTOR
        # ==========================

        if "video" in prompt.lower():

            workflow = engine.build_wan_video(
                prompt
            )

        else:

            workflow = engine.build_flux_image(
                prompt
            )


        # ==========================
        # SEND TO COMFY
        # ==========================

        response = send_workflow(
            workflow
        )


        if "prompt_id" not in response:

            return response



        # ==========================
        # FETCH RESULT
        # ==========================

        outputs = get_image(
            response["prompt_id"]
        )


        return {

            "engine":
                "ArchitectOS_Comfy_Adapter_v1",

            "prompt_id":
                response["prompt_id"],

            "outputs":
                outputs

        }