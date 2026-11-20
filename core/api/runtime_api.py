from core.runtime.runtime_controller import runtime_controller
from core.runtime.runtime_status import runtime_status


class RuntimeAPI:


    def __init__(self):

        self.controller = runtime_controller
        self.status_resolver = runtime_status


        print(
            "🌐 Runtime API Bridge v2 ACTIVE"
        )


    def set_mode(self, mode):

        self.controller.set_mode(
            mode
        )

        return self.status()


    def status(self):

        return self.status_resolver.status()


    def health(self):

        return self.status_resolver.status()["health"]



runtime_api = RuntimeAPI()