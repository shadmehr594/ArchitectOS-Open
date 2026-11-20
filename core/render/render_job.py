# ==========================================================
# ArchitectOS Render Job Manager v1
# Render Execution State Layer
# ==========================================================


import time



class RenderJobManager:


    VERSION = "1.0"



    def __init__(self):

        self.jobs = {}


        print(
            "🎬 RENDER JOB MANAGER v1 ONLINE"
        )



    # ======================================================
    # REGISTER JOB
    # ======================================================


    def register(
        self,
        job
    ):


        job_id = job.get(
            "job_id"
        )


        self.jobs[job_id] = job


        return job



    # ======================================================
    # UPDATE STATUS
    # ======================================================


    def update_status(
        self,
        job_id,
        status
    ):


        if job_id not in self.jobs:

            return None



        self.jobs[job_id][
            "status"
        ] = status



        self.jobs[job_id][
            "updated_at"
        ] = time.time()



        return self.jobs[job_id]



    # ======================================================
    # COMPLETE JOB
    # ======================================================


    def complete(
        self,
        job_id,
        result_asset=None
    ):


        if job_id not in self.jobs:

            return None



        self.jobs[job_id][
            "status"
        ] = "completed"



        self.jobs[job_id][
            "result_asset"
        ] = result_asset



        self.jobs[job_id][
            "completed_at"
        ] = time.time()



        return self.jobs[job_id]



    # ======================================================
    # GET JOB
    # ======================================================


    def get(
        self,
        job_id
    ):


        return self.jobs.get(
            job_id
        )