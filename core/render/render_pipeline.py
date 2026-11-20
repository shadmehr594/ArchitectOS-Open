# ==========================================================
# ArchitectOS Full Render Pipeline v1
# Design -> Render -> Memory -> Evolution
# ==========================================================


from core.render.render_orchestrator import RenderRuntimeOrchestrator
from core.render.render_result import RenderResultManager
from core.render.render_memory import RenderMemoryBridge
from core.render.render_evolution import RenderEvolutionBridge



class FullRenderPipeline:


    VERSION = "1.0"



    def __init__(self):

        self.renderer = RenderRuntimeOrchestrator()

        self.results = RenderResultManager()

        self.memory = RenderMemoryBridge()

        self.evolution = RenderEvolutionBridge()


        print(
            "🔄 FULL RENDER PIPELINE v1 ONLINE"
        )



    # ======================================================
    # RUN PIPELINE
    # ======================================================


    def run(
        self,
        project_id,
        design,
        engine="flux"
    ):


        context = {

            "context_id":
                "pipeline_context",

            "project_id":
                project_id,

            "engine":
                engine,

            "design":
                design,

            "assets":
                []

        }



        render_job = self.renderer.render(
            context
        )



        task = render_job.get(
            "task"
        )



        result = {

            "result_id":
                "pipeline_result",

            "job_id":
                task.get(
                    "task_id"
                ),

            "project_id":
                project_id,

            "engine":
                engine,

            "asset":
            {

                "file":
                    "pending_render_output"

            },

            "status":
                "stored"

        }



        stored = self.memory.store(
            result
        )


        evolution = self.evolution.register(
            result
        )


        return {

            "render":
                render_job,

            "memory":
                stored,

            "evolution":
                evolution

        }