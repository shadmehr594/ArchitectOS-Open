# ==================================================
# ArchitectOS Session Context Adapter v79
# ==================================================


class ArchitectOSSessionContext:


    VERSION = "79.0"



    def __init__(self):

        print(
            "🗂️ ArchitectOS Session Context v79.0 ACTIVE"
        )


        self.sessions = {}



    # ==================================================
    # CREATE / UPDATE SESSION
    # ==================================================

    def update(
        self,
        session_id,
        data
    ):


        if session_id not in self.sessions:

            self.sessions[session_id] = []



        self.sessions[session_id].append(
            data
        )



        return {

            "session_id":
            session_id,


            "items":
            len(
                self.sessions[session_id]
            )

        }



    # ==================================================
    # GET CONTEXT
    # ==================================================

    def get(
        self,
        session_id
    ):


        return {

            "session_id":
            session_id,


            "context":
            self.sessions.get(
                session_id,
                []
            )

        }



    # ==================================================
    # CLEAR
    # ==================================================

    def clear(
        self,
        session_id
    ):


        if session_id in self.sessions:

            del self.sessions[session_id]


        return {

            "status":
            "cleared",

            "session_id":
            session_id

        }