# ==========================================================
# ArchitectOS Project Snapshot Manager v1
# Full Project State Snapshot Layer
# ==========================================================


import time
import uuid



class ProjectSnapshotManager:


    VERSION = "1.0"



    def __init__(self):

        self.snapshots = {}


        print(
            "📸 PROJECT SNAPSHOT MANAGER v1 ONLINE"
        )



    # ======================================================
    # CREATE SNAPSHOT
    # ======================================================


    def create_snapshot(
        self,
        project_id,
        state,
        label=None
    ):


        if project_id not in self.snapshots:

            self.snapshots[project_id] = []



        snapshot = {

            "snapshot_id":
                "snapshot_"
                + str(uuid.uuid4())[:8],

            "project_id":
                project_id,

            "label":
                label or "snapshot",

            "state":
                state,

            "created_at":
                time.time()

        }



        self.snapshots[project_id].append(
            snapshot
        )


        return snapshot



    # ======================================================
    # LIST SNAPSHOTS
    # ======================================================


    def list_snapshots(
        self,
        project_id
    ):


        return self.snapshots.get(
            project_id,
            []
        )



    # ======================================================
    # LATEST SNAPSHOT
    # ======================================================


    def latest(
        self,
        project_id
    ):


        items = self.list_snapshots(
            project_id
        )


        if not items:

            return None


        return items[-1]