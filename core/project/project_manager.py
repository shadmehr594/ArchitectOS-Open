# ==========================================================
# ArchitectOS Project Manager v1
# Project Lifecycle Controller
# ==========================================================


import uuid
import time

from core.project.project_store import ProjectStore



class ProjectManager:


    VERSION = "1.0"



    def __init__(self):

        self.store = ProjectStore()


        print(
            "🚀 PROJECT MANAGER v1 ONLINE"
        )



    # ======================================================
    # CREATE PROJECT
    # ======================================================


    def create_project(
        self,
        name
    ):


        project_id = (
            "project_"
            +
            str(uuid.uuid4())[:8]
        )


        project = {

            "project_id":
                project_id,

            "name":
                name,

            "created_at":
                time.time(),

            "status":
                "created"

        }



        self.store.save(
            project_id,
            "project.json",
            project
        )


        return project



    # ======================================================
    # SAVE DESIGN
    # ======================================================


    def save_design(
        self,
        project_id,
        design
    ):


        return self.store.save(
            project_id,
            "design.json",
            design
        )



    # ======================================================
    # LOAD PROJECT
    # ======================================================


    def load_project(
        self,
        project_id
    ):


        return self.store.load(
            project_id,
            "project.json"
        )



    # ======================================================
    # LOAD DESIGN
    # ======================================================


    def load_design(
        self,
        project_id
    ):


        return self.store.load(
            project_id,
            "design.json"
        )



    # ======================================================
    # PROJECT STATUS
    # ======================================================


    def status(
        self,
        project_id
    ):


        project = self.load_project(
            project_id
        )


        if not project:

            return {

                "status":
                    "missing"

            }



        return {

            "status":
                project.get(
                    "status"
                ),

            "project_id":
                project.get(
                    "project_id"
                )

        }