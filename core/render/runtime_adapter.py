# ==========================================================
# ArchitectOS Runtime Render Adapter v1
# ComfyUI / WAN Runtime Contract Layer
# ==========================================================


import time
import uuid



class RuntimeRenderAdapter:


    VERSION = "1.0"



    SUPPORTED_RUNTIME = {

        "flux":
            "comfyui",

        "wan":
            "wan_runtime"

    }



    def __init__(self):

        self.tasks = {}


        print(
            "⚙️ RUNTIME RENDER ADAPTER v1 ONLINE"
        )



    # ======================================================
    # CHECK RUNTIME
    # ======================================================


    def runtime_for_engine(
        self,
        engine
    ):


        return self.SUPPORTED_RUNTIME.get(
            engine
        )



    # ======================================================
    # PREPARE TASK
    # ======================================================


    def prepare(
        self,
        request
    ):


        engine = request.get(
            "engine"
        )


        runtime = self.runtime_for_engine(
            engine
        )


        if not runtime:

            return {
                "error":
                    "runtime_not_found"
            }



        task = {

            "task_id":
                "runtime_task_"
                + str(uuid.uuid4())[:8],

            "request_id":
                request.get(
                    "request_id"
                ),

            "project_id":
                request.get(
                    "project_id"
                ),

            "engine":
                engine,

            "runtime":
                runtime,

            "payload":
                request.get(
                    "payload"
                ),

            "status":
                "ready",

            "created_at":
                time.time()

        }



        self.tasks[
            task["task_id"]
        ] = task



        return task



    # ======================================================
    # GET TASK
    # ======================================================


    def get(
        self,
        task_id
    ):


        return self.tasks.get(
            task_id
        )