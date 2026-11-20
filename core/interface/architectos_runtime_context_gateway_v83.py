# ==================================================
# ArchitectOS Runtime Context Gateway v83
# ==================================================


class ArchitectOSRuntimeContextGateway:


    VERSION = "83.0"



    def __init__(
        self,
        session_manager,
        runtime
    ):


        print(
            "🌐 ArchitectOS Runtime Context Gateway v83.0 ACTIVE"
        )


        self.session_manager = session_manager
        self.runtime = runtime



    # ==================================================
    # PROCESS REQUEST
    # ==================================================

    def process(
        self,
        request
    ):


        if request is None:

            request = {}



        session_id = request.get(

            "session_id",

            "session_001"

        )


        command = request.get(

            "command",

            {}

        )



        # ==========================
        # LOAD SESSION
        # ==========================

        session = self.session_manager.get_session(

            session_id

        )



        runtime_request = {


            "command":

            command,


            "session":

            session

        }



        # ==========================
        # RUN GLOBAL RUNTIME
        # ==========================

        result = self.runtime.process(

            runtime_request

        )



        # ==========================
        # SAVE SESSION UPDATE
        # ==========================

        self.session_manager.update_session(

            session_id,

            {

                "command":

                command,


                "result":

                result

            }

        )



        return {


            "engine":

            f"architectos_runtime_context_gateway_v{self.VERSION}",


            "status":

            "completed",


            "session":

            session_id,


            "runtime":

            result

        }