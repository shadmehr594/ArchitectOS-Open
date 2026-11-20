# ==========================================================
# ArchitectOS Render Evolution Bridge v1
# Render History -> Project Evolution Layer
# ==========================================================


import time



class RenderEvolutionBridge:


    VERSION = "1.0"



    def __init__(self):

        self.history = {}

        print(
            "🧬 RENDER EVOLUTION BRIDGE v1 ONLINE"
        )



    # ======================================================
    # REGISTER EVOLUTION EVENT
    # ======================================================


    def register(
        self,
        render_memory
    ):


        project_id = render_memory.get(
            "project_id"
        )


        if project_id not in self.history:

            self.history[project_id] = []



        event = {

            "type":
                "render_update",

            "engine":
                render_memory.get(
                    "engine"
                ),

            "asset":
                render_memory.get(
                    "asset"
                ),

            "result_id":
                render_memory.get(
                    "result_id"
                ),

            "time":
                time.time()

        }


        self.history[project_id].append(
            event
        )


        return event



    # ======================================================
    # PROJECT HISTORY
    # ======================================================


    def get_history(
        self,
        project_id
    ):


        return self.history.get(
            project_id,
            []
        )



    # ======================================================
    # LATEST EVOLUTION
    # ======================================================


    def latest(
        self,
        project_id
    ):


        items = self.get_history(
            project_id
        )


        if not items:

            return None


        return items[-1]