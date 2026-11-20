# ==========================================================
# ArchitectOS Voice Gateway v1
#
# API Boundary for Voice System
#
# UI/API -> Voice Gateway -> Conversation Loop
#
# Runtime owns Intelligence
# ==========================================================


import uuid



class VoiceGateway:


    VERSION = "1.0"



    def __init__(
        self,
        conversation_loop
    ):


        self.loop = conversation_loop


        self.sessions = {}


        print(
            "🌐 VOICE GATEWAY v1 ONLINE"
        )



    # ======================================================
    # CREATE SESSION
    # ======================================================


    def create_session(
        self
    ):


        session_id = str(
            uuid.uuid4()
        )


        result = self.loop.start()


        self.sessions[session_id] = {

            "active": True,

            "loop_session": result

        }


        return {

            "session_id": session_id,

            "status": "created",

            "data": result

        }



    # ======================================================
    # SEND MESSAGE
    # ======================================================


    def send(
        self,
        session_id,
        text
    ):


        if session_id not in self.sessions:


            return {

                "error": "invalid session"

            }



        if not self.sessions[session_id]["active"]:


            return {

                "error": "session closed"

            }



        result = self.loop.process(
            text
        )


        return {

            "session_id": session_id,

            "response": result

        }



    # ======================================================
    # CLOSE SESSION
    # ======================================================


    def close(
        self,
        session_id
    ):


        if session_id not in self.sessions:


            return {

                "error": "invalid session"

            }



        result = self.loop.stop()


        self.sessions[session_id]["active"] = False


        return {

            "session_id": session_id,

            "status": "closed",

            "data": result

        }