# ==========================================================
# ArchitectOS ComfyUI Connector v2
# Flux Runtime Connector + Execution
# ==========================================================


import time

from core.render.comfy_http_runtime import ComfyHTTPRuntime



class ComfyUIConnector:


    VERSION = "2.0"



    def __init__(self):

        self.endpoint = (
            "http://127.0.0.1:8188"
        )

        self.workflow = "flux"


        self.runtime = ComfyHTTPRuntime(
            self.endpoint
        )


        print(
            "🚀 COMFYUI CONNECTOR v2 ONLINE"
        )



    # ======================================================
    # CREATE PAYLOAD
    # ======================================================


    def prepare_job(
        self,
        task
    ):


        return {

            "runtime":
                "comfyui",

            "endpoint":
                self.endpoint,

            "workflow":
                self.workflow,

            "task_id":
                task.get(
                    "task_id"
                ),

            "project_id":
                task.get(
                    "project_id"
                ),

            "payload":
                task.get(
                    "payload"
                ),

            "status":
                "prepared",

            "created_at":
                time.time()

        }



    # ======================================================
    # EXECUTE
    # ======================================================


    def execute_job(
        self,
        workflow
    ):


        return self.runtime.submit(
            workflow
        )