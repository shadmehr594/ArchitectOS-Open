# ==================================================
# ArchitectOS Session Manager Adapter v82
# ==================================================


class ArchitectOSSessionManager:


    VERSION = "82.0"



    def __init__(
        self,
        session_context,
        persistence
    ):


        print(
            "🗂️ ArchitectOS Session Manager v82.0 ACTIVE"
        )


        self.session_context = session_context
        self.persistence = persistence



    # ==================================================
    # GET SESSION
    # ==================================================

    def get_session(
        self,
        session_id
    ):


        context = self.session_context.get(
            session_id
        )


        if not context:

            context = self.persistence.load(
                session_id
            )


        return {

            "session_id":
            session_id,


            "context":
            context

        }



    # ==================================================
    # UPDATE SESSION
    # ==================================================

    def update_session(
        self,
        session_id,
        data
    ):


        self.session_context.update(

            session_id,

            data

        )


        current = self.session_context.get(
            session_id
        )


        self.persistence.save(

            session_id,

            current

        )


        return {

            "status":
            "updated",


            "session":
            session_id

        }