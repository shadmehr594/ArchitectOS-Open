# ==========================================================
# ArchitectOS Chat Render Bridge v1
# Chat -> Design -> Render Pipeline
# ==========================================================


from core.render.render_orchestrator import RenderRuntimeOrchestrator



class ChatRenderBridge:


    VERSION = "1.0"



    def __init__(self):

        self.renderer = RenderRuntimeOrchestrator()


        print(
            "🌉 CHAT RENDER BRIDGE v1 ONLINE"
        )



    # ======================================================
    # DESIGN TO RENDER
    # ======================================================


    def render_design(
        self,
        project_id,
        design,
        engine="flux"
    ):


        context = {

            "context_id":
                "chat_design_context",

            "project_id":
                project_id,

            "engine":
                engine,

            "design":
                design,

            "assets":
                []

        }


        return self.renderer.render(
            context
        )