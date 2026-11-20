# ==========================================================
# ArchitectOS Voice Session Engine v1
#
# Voice Conversation Session State
# Runtime independent
# ==========================================================


import uuid
import time



class VoiceSession:


    VERSION = "1.0"



    def __init__(self):


        self.session_id = None

        self.started_at = None

        self.last_activity = None

        self.active = False

        self.history = []


        print(
            "🎙️ VOICE SESSION v1 ONLINE"
        )



    # ======================================================
    # START
    # ======================================================


    def start(self):


        self.session_id = str(
            uuid.uuid4()
        )


        now = time.time()


        self.started_at = now

        self.last_activity = now

        self.active = True


        return self.state()



    # ======================================================
    # UPDATE
    # ======================================================


    def update(
        self,
        user_input,
        result=None
    ):


        if not self.active:

            self.start()


        self.last_activity = time.time()



        self.history.append(
            {
                "input": user_input,
                "result": result
            }
        )



        return self.state()



    # ======================================================
    # STATE
    # ======================================================


    def state(self):


        return {

            "session_id": self.session_id,

            "active": self.active,

            "messages": len(self.history),

            "started_at": self.started_at,

            "last_activity": self.last_activity

        }



    # ======================================================
    # CLOSE
    # ======================================================


    def close(self):


        self.active = False


        return self.state()