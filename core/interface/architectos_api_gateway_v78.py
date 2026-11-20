# ==================================================
# ArchitectOS API Gateway v78
# ==================================================

from core.intelligence.architectos_command_interface_v76 import (
    ArchitectOSCommandInterface
)

from core.intelligence.architectos_response_formatter_v77 import (
    ArchitectOSResponseFormatter
)



class ArchitectOSAPIGateway:


    VERSION = "78.0"



    def __init__(self):

        print(
            "🌐 ArchitectOS API Gateway v78.0 ACTIVE"
        )


        self.command_interface = (
            ArchitectOSCommandInterface()
        )


        self.formatter = (
            ArchitectOSResponseFormatter()
        )



    # ==================================================
    # API ENTRY
    # ==================================================

    def request(
        self,
        payload
    ):


        raw_response = (
            self.command_interface.execute(
                payload
            )
        )


        formatted_response = (
            self.formatter.format(
                raw_response
            )
        )


        return {

            "engine":
            f"architectos_api_gateway_v{self.VERSION}",


            "status":
            "success",


            "response":
            formatted_response

        }