# ==========================================================
# ArchitectOS Project Runtime v1
# Runtime -> Project Integration
# ==========================================================


from core.project.project_manager import ProjectManager



class ProjectRuntime:


    VERSION = "1.0"



    def __init__(self):

        self.manager = ProjectManager()


        print(
            "🔗 PROJECT RUNTIME v1 ONLINE"
        )



    # ======================================================
    # CREATE DESIGN PROJECT
    # ======================================================


    def create_design_project(
        self,
        name,
        design_data
    ):


        project = self.manager.create_project(
            name
        )


        project_id = project["project_id"]



        self.manager.save_design(
            project_id,
            design_data
        )



        return {

            "project":
                project,

            "design_saved":
                True,

            "project_id":
                project_id

        }



    # ======================================================
    # GET PROJECT
    # ======================================================


    def get_project(
        self,
        project_id
    ):


        return {

            "project":
                self.manager.load_project(
                    project_id
                ),

            "design":
                self.manager.load_design(
                    project_id
                )

        }