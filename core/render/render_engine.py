# ==========================================================
# ArchitectOS Render Engine Bridge v1
# External Render Engine Contract Layer
# ==========================================================


import time
import uuid



class RenderEngineBridge:


    VERSION = "1.0"



    SUPPORTED_ENGINES = [
        "flux",
        "wan"
    ]



    def __init__(self):

        self.requests = {}

        print(
            "🔌 RENDER ENGINE BRIDGE v1 ONLINE"
        )



    # ======================================================
    # VALIDATE ENGINE
    # ======================================================


    def validate(
        self,
        engine
    ):


        return engine in self.SUPPORTED_ENGINES



    # ======================================================
    # CREATE ENGINE REQUEST
    # ======================================================


    def create_request(
        self,
        context,
        engine=None
    ):


        selected = (
            engine
            or context.get("engine")
        )


        if not self.validate(selected):

            return {
                "error":
                    "unsupported_engine"
            }



        request = {

            "request_id":
                "engine_req_"
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
                selected,

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
                "prepared",

            "created_at":
                time.time()

        }



        self.requests[
            request["request_id"]
        ] = request



        return request



    # ======================================================
    # GET REQUEST
    # ======================================================


    def get_request(
        self,
        request_id
    ):


        return self.requests.get(
            request_id
        )