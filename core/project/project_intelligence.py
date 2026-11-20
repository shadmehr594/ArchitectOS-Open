# ==========================================================
# ArchitectOS Project Intelligence v1
# Project Context Intelligence Layer
# ==========================================================


from core.project.project_state import ProjectState



class ProjectIntelligence:


    VERSION = "1.0"



    def __init__(self):

        self.state = ProjectState()


        print(
            "🧠 PROJECT INTELLIGENCE v1 ONLINE"
        )



    # ======================================================
    # REGISTER PROJECT
    # ======================================================


    def register_project(
        self,
        project_id
    ):


        return self.state.create(
            project_id
        )



    # ======================================================
    # PROCESS DESIGN
    # ======================================================


    def process_design(
        self,
        project_id,
        design
    ):


        return self.state.update_design(
            project_id,
            design
        )



    # ======================================================
    # PROCESS ASSET
    # ======================================================


    def process_asset(
        self,
        project_id,
        asset
    ):


        return self.state.add_asset(
            project_id,
            asset
        )



    # ======================================================
    # PROJECT SUMMARY
    # ======================================================


    def summary(
        self,
        project_id
    ):


        data = self.state.get(
            project_id
        )


        if not data:

            return {

                "project_id":
                    project_id,

                "status":
                    "unknown"

            }


        return {

            "project_id":
                project_id,

            "status":
                data["status"],

            "design":
                bool(data["design"]),

            "assets":
                len(data["assets"]),

            "operations":
                len(data["operations"])

        }