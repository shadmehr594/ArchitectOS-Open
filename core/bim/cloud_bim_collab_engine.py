import time
import uuid
import copy


class CloudBIMCollabEngine:

    def __init__(self):

        # central BIM model store
        self.models = {}

        # version history (like git commits)
        self.versions = {}

        # active sessions
        self.sessions = {}

    # ======================
    # CREATE PROJECT
    # ======================
    def create_project(self, project_name, base_model=None):

        project_id = str(uuid.uuid4())

        self.models[project_id] = base_model or self._empty_model()

        self.versions[project_id] = []

        return project_id

    # ======================
    # USER SESSION JOIN
    # ======================
    def join_session(self, project_id, user_id):

        if project_id not in self.sessions:
            self.sessions[project_id] = []

        self.sessions[project_id].append(user_id)

        return {
            "status": "joined",
            "project": project_id,
            "user": user_id
        }

    # ======================
    # APPLY CHANGE (COLLAB EDIT)
    # ======================
    def apply_change(self, project_id, user_id, change):

        model = self.models[project_id]

        # snapshot before change (VERSION CONTROL)
        snapshot = copy.deepcopy(model)

        # apply change
        model = self._merge_change(model, change)

        self.models[project_id] = model

        # save version
        self._commit(project_id, user_id, snapshot, model)

        # broadcast update
        self._broadcast(project_id, change)

        return model

    # ======================
    # VERSION CONTROL (LIKE GIT)
    # ======================
    def _commit(self, project_id, user_id, before, after):

        version = {
            "id": str(uuid.uuid4()),
            "user": user_id,
            "timestamp": time.time(),
            "before": before,
            "after": after
        }

        self.versions[project_id].append(version)

    # ======================
    # CONFLICT DETECTION
    # ======================
    def detect_conflicts(self, project_id):

        versions = self.versions[project_id]

        conflicts = []

        for i in range(len(versions) - 1):

            v1 = versions[i]
            v2 = versions[i + 1]

            if v1["after"] == v2["after"]:
                continue

            if self._overlapping_changes(v1, v2):
                conflicts.append((v1["id"], v2["id"]))

        return conflicts

    # ======================
    # BROADCAST UPDATES
    # ======================
    def _broadcast(self, project_id, change):

        users = self.sessions.get(project_id, [])

        for u in users:
            print(f"📡 Sending update to {u}: {change}")

    # ======================
    # MODEL MERGER
    # ======================
    def _merge_change(self, model, change):

        # simple merge logic (can become semantic BIM diff engine)
        if "walls" in change:
            model["walls"] = change["walls"]

        if "floors" in change:
            model["floors"] = change["floors"]

        if "structure" in change:
            model["structure"] = change["structure"]

        return model

    # ======================
    # EMPTY MODEL
    # ======================
    def _empty_model(self):

        return {
            "walls": [],
            "floors": 0,
            "structure": {}
        }