# ==========================================================
# ArchitectOS Project State v1
# Live Project Context Layer
# ==========================================================


import time



class ProjectState:


    VERSION = "1.0"



    def __init__(self):

        self.states = {}


        print(
            "🧠 PROJECT STATE v1 ONLINE"
        )



    # ======================================================
    # CREATE STATE
    # ======================================================


    def create(
        self,
        project_id
    ):


        state = {

            "project_id":
                project_id,

            "status":
                "active",

            "design":
                None,

            "assets":
                [],

            "operations":
                [],

            "created_at":
                time.time(),

            "updated_at":
                time.time()

        }


        self.states[project_id] = state


        return state



    # ======================================================
    # UPDATE DESIGN
    # ======================================================


    def update_design(
        self,
        project_id,
        design
    ):


        state = self.states.get(
            project_id
        )


        if not state:

            state = self.create(
                project_id
            )


        state["design"] = design


        state["operations"].append(
            {
                "type":"design_update",
                "time":time.time()
            }
        )


        state["updated_at"] = time.time()


        return state



    # ======================================================
    # ADD ASSET
    # ======================================================


    def add_asset(
        self,
        project_id,
        asset
    ):


        state = self.states.get(
            project_id
        )


        if not state:

            state = self.create(
                project_id
            )


        state["assets"].append(
            asset
        )


        state["operations"].append(
            {
                "type":"asset_added",
                "time":time.time()
            }
        )


        state["updated_at"] = time.time()


        return state



    # ======================================================
    # GET STATE
    # ======================================================


    def get(
        self,
        project_id
    ):


        return self.states.get(
            project_id
        )