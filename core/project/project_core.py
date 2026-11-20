# ==========================================================
# ArchitectOS Project Core v1
# Unified Project Context Layer
# ==========================================================


from core.project.project_state import ProjectState
from core.project.project_version import ProjectVersionManager
from core.project.project_snapshot import ProjectSnapshotManager



class ProjectCore:


    VERSION = "1.0"



    def __init__(self):

        self.state = ProjectState()

        self.version = ProjectVersionManager()

        self.snapshot = ProjectSnapshotManager()


        print(
            "🧠 PROJECT CORE v1 ONLINE"
        )



    # ======================================================
    # CREATE PROJECT CONTEXT
    # ======================================================


    def create_project(
        self,
        project_id
    ):


        return self.state.create(
            project_id
        )



    # ======================================================
    # UPDATE DESIGN
    # ======================================================


    def update_design(
        self,
        project_id,
        design
    ):


        return self.state.update_design(
            project_id,
            design
        )



    # ======================================================
    # CREATE VERSION
    # ======================================================


    def create_version(
        self,
        project_id,
        label=None
    ):


        current = self.state.get(
            project_id
        )


        return self.version.create_version(
            project_id,
            current,
            label
        )



    # ======================================================
    # CREATE SNAPSHOT
    # ======================================================


    def create_snapshot(
        self,
        project_id,
        label=None
    ):


        current = self.state.get(
            project_id
        )


        return self.snapshot.create_snapshot(
            project_id,
            current,
            label
        )



    # ======================================================
    # PROJECT SUMMARY
    # ======================================================


    def summary(
        self,
        project_id
    ):


        state = self.state.get(
            project_id
        )


        return {

            "project_id":
                project_id,

            "state":
                state,

            "versions":
                len(
                    self.version.list_versions(
                        project_id
                    )
                ),

            "snapshots":
                len(
                    self.snapshot.list_snapshots(
                        project_id
                    )
                )

        }