import time
import uuid


class RealtimeBIMCollab:

    def __init__(self):

        self.sessions = {}
        self.history = []

    # ======================
    # CREATE SESSION
    # ======================
    def create_session(self, project_id):

        session_id = str(uuid.uuid4())

        self.sessions[session_id] = {
            "project_id": project_id,
            "state": {},
            "users": [],
            "last_update": time.time()
        }

        return session_id

    # ======================
    # JOIN SESSION
    # ======================
    def join(self, session_id, user):

        self.sessions[session_id]["users"].append(user)

        return {
            "status": "joined",
            "session": session_id
        }

    # ======================
    # UPDATE BIM STATE
    # ======================
    def update(self, session_id, user, new_state):

        session = self.sessions[session_id]

        session["state"] = self._merge(session["state"], new_state)
        session["last_update"] = time.time()

        self.history.append({
            "session": session_id,
            "user": user,
            "change": new_state
        })

        return session["state"]

    # ======================
    # SIMPLE MERGE ENGINE
    # ======================
    def _merge(self, old, new):

        merged = old.copy()
        merged.update(new)
        return merged