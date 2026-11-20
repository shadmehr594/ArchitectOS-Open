# ==================================================
# ArchitectOS Runtime Event Bus v89
# ==================================================


class ArchitectOSEventBus:


    VERSION = "89.0"



    def __init__(self):


        print(
            "📡 ArchitectOS Event Bus v89.0 ACTIVE"
        )


        self.events = []

        self.listeners = []



    # ==================================================
    # REGISTER LISTENER
    # ==================================================

    def register(
        self,
        listener
    ):


        self.listeners.append(

            listener

        )


        return {


            "status":

            "registered",


            "listeners":

            len(self.listeners)

        }



    # ==================================================
    # PUBLISH EVENT
    # ==================================================

    def publish(
        self,
        event
    ):


        event_record = {


            "index":

            len(self.events) + 1,


            "event":

            event

        }



        self.events.append(

            event_record

        )



        for listener in self.listeners:


            listener.process(

                event

            )



        return {


            "engine":

            f"architectos_event_bus_v{self.VERSION}",


            "status":

            "published",


            "event_id":

            event_record["index"],


            "listeners_notified":

            len(self.listeners)

        }



    # ==================================================
    # READ EVENTS
    # ==================================================

    def get_events(self):

        return self.events