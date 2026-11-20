# ==========================================================
# ArchitectOS Runtime Status Resolver v1
# Active Runtime + Availability + Health
# ==========================================================


from core.runtime.runtime_selector import runtime_selector



class RuntimeStatus:


    def __init__(self):

        self.selector = runtime_selector


        print(
            "📡 Runtime Status Resolver v1 ACTIVE"
        )



    # ======================================================
    # FULL STATUS
    # ======================================================

    def status(self):


        active_runtime = (
            self.selector.get_runtime()
        )


        health = (
            self.selector.health()
        )


        return {


            "mode":

                self.selector.mode.mode,


            "active_runtime":

                active_runtime.engine,


            "health":

                health,


            "available_runtime":

                health.get(
                    "details",
                    {}
                ).get(
                    "runtime"
                )


        }



# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


runtime_status = RuntimeStatus()