import uuid
import time


class BIMCloudPlatform:

    def __init__(self):

        self.projects = {}
        self.users = {}

    # ======================
    # CREATE PROJECT
    # ======================
    def create_project(self, name, owner):

        pid = str(uuid.uuid4())

        self.projects[pid] = {
            "name": name,
            "owner": owner,
            "state": {},
            "collaborators": [owner],
            "created_at": time.time()
        }

        return pid

    # ======================
    # ADD USER
    # ======================
    def add_user(self, user_id, role="architect"):

        self.users[user_id] = {
            "role": role,
            "projects": []
        }

    # ======================
    # SHARE PROJECT
    # ======================
    def share_project(self, project_id, user_id):

        if project_id in self.projects:

            self.projects[project_id]["collaborators"].append(user_id)

            self.users[user_id]["projects"].append(project_id)

        return self.projects[project_id]

    # ======================
    # UPDATE PROJECT STATE
    # ======================
    def update_state(self, project_id, new_state):

        project = self.projects[project_id]

        project["state"].update(new_state)
        project["updated_at"] = time.time()

        return project["state"]

    # ======================
    # GET PROJECT
    # ======================
    def get_project(self, project_id):

        return self.projects.get(project_id, None)

    # ======================
    # LIST PROJECTS
    # ======================
    def list_projects(self):

        return [
            {
                "id": pid,
                "name": p["name"]
            }
            for pid, p in self.projects.items()
        ]