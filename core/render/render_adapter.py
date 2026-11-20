# ==========================================================
# ArchitectOS Render Pipeline Adapter v1
# Render Engine Abstraction Layer
# ==========================================================


import time
import uuid



class RenderPipelineAdapter:


    VERSION = "1.0"



    def __init__(self):

        self.jobs = {}

        print(
            "⚙️ RENDER PIPELINE ADAPTER v1 ONLINE"
        )



    # ======================================================
    # CREATE RENDER JOB
    # ======================================================


    def create_job(
        self,
        context,
        engine=None
    ):


        selected_engine = (
            engine
            or context.get("engine")
        )


        job = {

            "job_id":
                "render_job_"
                + str(uuid.uuid4())[:8],

            "context_id":
                context.get(
                    "context_id"
                ),

            "project_id":
                context.get(
                    "project_id"
                ),

            "engine":
                selected_engine,

            "payload":
            {

                "design":
                    context.get(
                        "design"
                    ),

                "assets":
                    context.get(
                        "assets",
                        []
                    )

            },

            "status":
                "queued",

            "created_at":
                time.time()

        }


        self.jobs[
            job["job_id"]
        ] = job


        return job



    # ======================================================
    # ENGINE VALIDATION
    # ======================================================


    def validate_engine(
        self,
        engine
    ):


        return engine in [
            "flux",
            "wan"
        ]



    # ======================================================
    # GET JOB
    # ======================================================


    def get_job(
        self,
        job_id
    ):


        return self.jobs.get(
            job_id
        )