# ==================================================
# ArchitectOS Runtime Event Router v90
# ==================================================


class ArchitectOSEventRouter:


    VERSION = "90.0"



    def __init__(
        self,
        event_bus=None
    ):


        print(
            "🔀 ArchitectOS Event Router v90.0 ACTIVE"
        )


        self.event_bus = event_bus

        self.routes = {}



    # ==================================================
    # REGISTER ROUTE
    # ==================================================

    def register_route(
        self,
        event_type,
        handler
    ):


        self.routes[event_type] = handler


        return {


            "status":

            "route_registered",


            "event_type":

            event_type

        }



    # ==================================================
    # HANDLE EVENT
    # ==================================================

    def process(
        self,
        event
    ):


        event_type = event.get(

            "type",

            "unknown"

        )


        handler = self.routes.get(

            event_type

        )



        if handler:


            result = handler.process(

                event

            )


            return {


                "engine":

                f"architectos_event_router_v{self.VERSION}",


                "status":

                "routed",


                "event_type":

                event_type,


                "handler_result":

                result

            }



        return {


            "engine":

            f"architectos_event_router_v{self.VERSION}",


            "status":

            "ignored",


            "reason":

            "no_handler",


            "event_type":

            event_type

        }



    # ==================================================
    # CONNECT TO BUS
    # ==================================================

    def connect(self):


        if self.event_bus:


            self.event_bus.register(

                self

            )


            return {


                "status":

                "connected"

            }



        return {


            "status":

            "no_event_bus"

        }



    # ==================================================
    # EVENT BUS CALLBACK
    # ==================================================

    def publish_callback(
        self,
        event
    ):


        return self.process(

            event

        )