# ==========================================================
# ArchitectOS Render Runtime Orchestrator v2
# Unified Design/Image Render Controller
# ==========================================================


from core.render.render_engine import RenderEngineBridge
from core.render.runtime_adapter import RuntimeRenderAdapter

from core.render.render_runtime import RenderRuntime

from core.render.render_result_bridge import RenderResultBridge



class RenderRuntimeOrchestrator:


    VERSION = "2.0"



    def __init__(self):

        self.engine = RenderEngineBridge()

        self.runtime = RuntimeRenderAdapter()

        self.renderer = RenderRuntime()

        self.result_bridge = RenderResultBridge()


        print(
            "🚀 RENDER RUNTIME ORCHESTRATOR v2 ONLINE"
        )



    # ======================================================
    # MAIN RENDER
    # ======================================================


    def render(
        self,
        context
    ):


        # ---------------------------------
        # CREATE REQUEST
        # ---------------------------------

        request = self.engine.create_request(
            context
        )


        if "error" in request:

            return request



        # ---------------------------------
        # PREPARE TASK
        # ---------------------------------

        task = self.runtime.prepare(
            request
        )


        if task.get("status") != "ready":

            return task



        # ---------------------------------
        # EXTRACT DESIGN
        # ---------------------------------

        payload = task.get(
            "payload",
            {}
        )


        design = payload.get(
            "design",
            {}
        )


        assets = payload.get(
            "assets",
            []
        )



        # ---------------------------------
        # REAL COMFY EXECUTION
        # ---------------------------------

        render_result = self.renderer.render(

            project_id=

                request.get(
                    "project_id",
                    "default"
                ),

            design=design,

            engine=

                request.get(
                    "engine",
                    "flux"
                ),

            image_asset=

                assets[0]
                if assets
                else None

        )



        # ---------------------------------
        # RESOLVE IMAGE
        # ---------------------------------

        resolved = self.result_bridge.resolve(
            {
                "execution":
                    render_result.get(
                        "execution",
                        {}
                    )
            }
        )



        return {

            "request":
                request,


            "task":
                task,


            "render":
                render_result,


            "result":
                resolved

        }