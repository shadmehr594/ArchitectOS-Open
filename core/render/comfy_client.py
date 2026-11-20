# ==========================================================
# ArchitectOS ComfyUI API Client v1
# Real ComfyUI Communication Layer
# ==========================================================


import time
import uuid



class ComfyUIClient:


    VERSION = "1.0"



    def __init__(
        self,
        endpoint="http://127.0.0.1:8188"
    ):

        self.endpoint = endpoint

        self.executions = {}


        print(
            "🎨 COMFYUI API CLIENT v1 ONLINE"
        )



    # ======================================================
    # PREPARE PROMPT
    # ======================================================


    def prepare_prompt(
        self,
        workflow
    ):


        prompt_id = (
            "prompt_"
            + str(uuid.uuid4())[:8]
        )


        record = {

            "prompt_id":
                prompt_id,

            "endpoint":
                self.endpoint,

            "workflow":
                workflow,

            "status":
                "prepared",

            "created_at":
                time.time()

        }


        self.executions[
            prompt_id
        ] = record


        return record



    # ======================================================
    # STATUS
    # ======================================================


    def get_status(
        self,
        prompt_id
    ):

        return self.executions.get(
            prompt_id
        )