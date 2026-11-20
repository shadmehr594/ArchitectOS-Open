# ==================================================
# ArchitectOS API Session Bridge v80
# ==================================================


class ArchitectOSAPISessionBridge:


    VERSION = "80.0"



    def __init__(
        self,
        api_gateway,
        session_context
    ):


        print(
            "🌉 ArchitectOS API Session Bridge v80.0 ACTIVE"
        )


        self.api_gateway = api_gateway
        self.session_context = session_context



    # ==================================================
    # PROCESS COMMAND WITH SESSION
    # ==================================================

    def process(
        self,
        session_id,
        command
    ):


        context = self.session_context.get(
            session_id
        )



        request = {

            "session_id":
            session_id,


            "command":
            command,


            "context":
            context["context"]

        }



        response = self.api_gateway.process(
            request
        )



        self.session_context.update(

            session_id,

            {

                "command":
                command

            }

        )



        return {


            "engine":
            f"architectos_api_session_bridge_v{self.VERSION}",


            "status":
            "completed",


            "session":
            session_id,


            "response":
            response

        }