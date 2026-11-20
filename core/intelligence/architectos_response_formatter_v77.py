# ==================================================
# ArchitectOS Response Formatter Adapter v77
# ==================================================


class ArchitectOSResponseFormatter:


    VERSION = "77.0"



    def __init__(self):

        print(
            "📦 ArchitectOS Response Formatter v77.0 ACTIVE"
        )



    # ==================================================
    # FORMAT RESPONSE
    # ==================================================

    def format(
        self,
        response
    ):


        runtime = response.get(
            "output",
            {}
        )


        if "runtime" in runtime:

            runtime = runtime["runtime"]



        return {


            "engine":
            f"architectos_response_formatter_v{self.VERSION}",


            "status":
            "success",


            "decision":
            runtime.get(
                "decision",
                {}
            ),


            "memory":
            runtime.get(
                "memory",
                {}
            ),


            "agent":
            runtime.get(
                "agent",
                {}
            ),


            "source":
            response.get(
                "engine",
                "unknown"
            )

        }