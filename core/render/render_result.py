# ==========================================================
# ArchitectOS Render Result Integration v1
# Render Output Registry
# ==========================================================


import time
import uuid



class RenderResultManager:


    VERSION = "1.0"



    def __init__(self):

        self.results = {}

        print(
            "🖼️ RENDER RESULT MANAGER v1 ONLINE"
        )



    # ======================================================
    # SAVE RESULT
    # ======================================================


    def save_result(
        self,
        job,
        asset
    ):


        result = {

            "result_id":
                "result_"
                + str(uuid.uuid4())[:8],

            "job_id":
                job.get(
                    "job_id"
                ),

            "project_id":
                job.get(
                    "project_id"
                ),

            "engine":
                job.get(
                    "engine"
                ),

            "asset":
                asset,

            "created_at":
                time.time(),

            "status":
                "stored"

        }


        self.results[
            result["result_id"]
        ] = result


        return result



    # ======================================================
    # GET RESULT
    # ======================================================


    def get(
        self,
        result_id
    ):

        return self.results.get(
            result_id
        )



    # ======================================================
    # LIST PROJECT RESULTS
    # ======================================================


    def list_project_results(
        self,
        project_id
    ):


        return [

            r

            for r in self.results.values()

            if r.get(
                "project_id"
            ) == project_id

        ]