# ==========================================================
# ArchitectOS Project Version Manager v1
# Project History & Snapshot Layer
# ==========================================================


import time
import uuid



class ProjectVersionManager:


    VERSION = "1.0"



    def __init__(self):

        self.versions = {}


        print(
            "🗂️ PROJECT VERSION MANAGER v1 ONLINE"
        )



    # ======================================================
    # CREATE VERSION
    # ======================================================


    def create_version(
        self,
        project_id,
        data,
        label=None
    ):


        if project_id not in self.versions:

            self.versions[project_id] = []



        version_id = (
            "v"
            + str(len(self.versions[project_id]) + 1)
            .zfill(3)
        )



        version = {

            "version_id":
                version_id,

            "snapshot_id":
                "snapshot_"
                + str(uuid.uuid4())[:8],

            "project_id":
                project_id,

            "label":
                label or version_id,

            "data":
                data,

            "created_at":
                time.time()

        }



        self.versions[project_id].append(
            version
        )


        return version



    # ======================================================
    # LIST VERSIONS
    # ======================================================


    def list_versions(
        self,
        project_id
    ):


        return self.versions.get(
            project_id,
            []
        )



    # ======================================================
    # GET LATEST
    # ======================================================


    def latest(
        self,
        project_id
    ):


        items = self.list_versions(
            project_id
        )


        if not items:

            return None


        return items[-1]