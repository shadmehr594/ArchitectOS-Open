# ==========================================================
# ArchitectOS Runtime Selector v3
# Hybrid Runtime Decision Layer
# ==========================================================


from core.runtime_mode import RuntimeMode
from core.runtime.runtime_health import runtime_health
from core.runtime.runtime_state import runtime_state
from core.runtime.runtime_health import runtime_health



class RuntimeSelector:


    def __init__(self):

        self.mode = RuntimeMode()

        self.mode.set_mode(
            runtime_state.load_mode()
        )

        self.local_runtime = None

        self.online_runtime = None

        print(
            "🔀 Runtime Selector v4 ACTIVE"
        )



    # ======================================================
    # LOCAL RUNTIME
    # ======================================================

    def get_local_runtime(self):

        if self.local_runtime is None:

            from core.runtime.architectos_runtime import (
                ArchitectOSRuntime
            )

            self.local_runtime = ArchitectOSRuntime()


        return self.local_runtime



    # ======================================================
    # ONLINE RUNTIME
    # ======================================================

    def get_online_runtime(self):

        if self.online_runtime is None:

            from core.runtime.online_runtime import (
                OnlineRuntime
            )

            self.online_runtime = OnlineRuntime()


        return self.online_runtime



    # ======================================================
    # HYBRID CHECK
    # ======================================================

    def online_available(self):

        try:

            runtime = self.get_online_runtime()

            return True


        except Exception as e:

            print(
                "⚠️ ONLINE RUNTIME UNAVAILABLE:",
                e
            )

            return False



    # ======================================================
    # SELECT ACTIVE RUNTIME
    # ======================================================

    def get_runtime(self):


        mode = self.mode.mode


        print(
            "🔀 RUNTIME MODE:",
            mode
        )



        if mode == "online":

            return self.get_online_runtime()



        if mode == "offline":

            return self.get_local_runtime()



        # ==================================================
        # HYBRID
        # ==================================================

        if mode == "hybrid":


            health = runtime_health.status()


            print(
                "🩺 RUNTIME HEALTH:",
                health
            )


            if health["online"]:


                print(
                    "☁️ HYBRID SELECTED ONLINE"
                )


                return self.get_online_runtime()



            print(
                "🏗️ HYBRID FALLBACK OFFLINE"
            )


            return self.get_local_runtime()


    # ======================================================
    # HEALTH STATUS
    # ======================================================

    def health(self):


        status = runtime_health.status()


        print(
            "🩺 RUNTIME HEALTH:",
            status
        )


        return status



    # ======================================================
    # CHANGE MODE
    # ======================================================

    def set_mode(
        self,
        mode
    ):

        self.mode.set_mode(
            mode
        )

        runtime_state.save_mode(
            mode
        )



runtime_selector = RuntimeSelector()