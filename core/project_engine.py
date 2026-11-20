import uuid

class ProjectEngine:

    def create_project(self, name):

        return {
            "id": str(uuid.uuid4()),
            "name": name,
            "state": {}
        }

    def update_project(self, project, data):

        project["state"].update(data)
        return project