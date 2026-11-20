# ==========================================================
# ArchitectOS Runtime Health Checker v2
# Capability Probe Layer
# ==========================================================


class RuntimeHealthChecker:


    def __init__(self):

        print(
            "🩺 Runtime Health Checker v2 ACTIVE"
        )



    # ======================================================
    # ONLINE CAPABILITY CHECK
    # ======================================================

    def check_online(self):


        try:

            from core.runtime.online_runtime import (
                OnlineRuntime
            )


            available = (
                hasattr(
                    OnlineRuntime,
                    "run"
                )
            )


            return {

                "available":
                    available,

                "runtime":
                    "ONLINE_RUNTIME_V1"

            }


        except Exception as e:


            return {

                "available":
                    False,

                "runtime":
                    None,

                "error":
                    str(e)

            }



    # ======================================================
    # FULL HEALTH STATUS
    # ======================================================

    def status(self):


        online = self.check_online()


        return {

            "online":
                online["available"],


            "details":
                online

        }



# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


runtime_health = RuntimeHealthChecker()