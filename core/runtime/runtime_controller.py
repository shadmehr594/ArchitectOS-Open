# ==========================================================
# ArchitectOS Runtime Controller v1
# Runtime Management API Layer
# ==========================================================


from core.runtime.runtime_selector import runtime_selector



class RuntimeController:


    def __init__(self):

        self.selector = runtime_selector


        print(
            "🎛️ Runtime Controller v1 ACTIVE"
        )



    # ======================================================
    # SET MODE
    # ======================================================

    def set_mode(
        self,
        mode
    ):

        self.selector.set_mode(
            mode
        )


        return self.status()



    # ======================================================
    # GET CURRENT RUNTIME
    # ======================================================

    def get_runtime(self):


        runtime = self.selector.get_runtime()


        return runtime



    # ======================================================
    # STATUS
    # ======================================================

    def status(self):


        runtime = self.selector.get_runtime()


        return {

            "mode":
                self.selector.mode.mode,


            "runtime":
                runtime.engine,


            "health":
                self.selector.health()

        }



# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


runtime_controller = RuntimeController()