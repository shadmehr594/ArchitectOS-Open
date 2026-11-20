# ==========================================================
# ArchitectOS WAN Connector v1
# Video Runtime Connector
# ==========================================================


import time



class WANConnector:


    VERSION = "1.0"



    def __init__(self):

        self.endpoint = (
            "wan://runtime"
        )

        self.workflow = "wan_video"

        print(
            "🎥 WAN CONNECTOR v1 ONLINE"
        )



    # ======================================================
    # CREATE VIDEO PAYLOAD
    # ======================================================


    def prepare_job(
        self,
        task
    ):


        return {

            "runtime":
                "wan_runtime",

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