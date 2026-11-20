# ==========================================================
# ArchitectOS Render Execution Bridge v1
# Runtime Submit Layer
# ==========================================================


import time
import uuid



class RenderExecutionBridge:


    VERSION = "1.0"



    def __init__(self):

        self.executions = {}

        print(
            "⚡ RENDER EXECUTION BRIDGE v1 ONLINE"
        )



    # ======================================================
    # SUBMIT
    # ======================================================


    def submit(
        self,
        connector_payload
    ):


        runtime = connector_payload.get(
            "runtime"
        )


        if runtime == "comfyui":

            mode = "comfy_submit"


        elif runtime == "wan_runtime":

            mode = "wan_submit"


        else:

            return {
                "error":
                    "unknown_runtime"
            }



        execution = {

            "execution_id":
                "exec_"
                + str(uuid.uuid4())[:8],

            "task_id":
                connector_payload.get(
                    "task_id"
                ),

            "runtime":
                runtime,

            "mode":
                mode,

            "status":
                "submitted",

            "created_at":
                time.time()

        }



        self.executions[
            execution["execution_id"]
        ] = execution



        return execution



    # ======================================================
    # GET
    # ======================================================


    def get(
        self,
        execution_id
    ):

        return self.executions.get(
            execution_id
        )