# ==========================================================
# ArchitectOS Render Context Bridge v1
# Project -> Render Pipeline Contract
# ==========================================================


import time
import uuid



class RenderContextBridge:


    VERSION = "1.0"



    def __init__(self):

        self.contexts = {}

        print(
            "🎨 RENDER CONTEXT BRIDGE v1 ONLINE"
        )



    # ======================================================
    # CREATE RENDER CONTEXT
    # ======================================================


    def create_context(
        self,
        project_id,
        project_state,
        engine="flux"
    ):


        context = {

            "context_id":
                "render_ctx_"
                + str(uuid.uuid4())[:8],

            "project_id":
                project_id,

            "engine":
                engine,

            "design":
                project_state.get(
                    "design"
                ),

            "assets":
                project_state.get(
                    "assets",
                    []
                ),

            "created_at":
                time.time(),

            "status":
                "ready"

        }


        self.contexts[
            context["context_id"]
        ] = context


        return context



    # ======================================================
    # WAN READY CONTEXT
    # ======================================================


    def create_video_context(
        self,
        project_id,
        project_state
    ):


        return self.create_context(
            project_id,
            project_state,
            engine="wan"
        )



    # ======================================================
    # GET CONTEXT
    # ======================================================


    def get(
        self,
        context_id
    ):

        return self.contexts.get(
            context_id
        )