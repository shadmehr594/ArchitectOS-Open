class Debugger:

    def __init__(self, emitter=None):
        self.emitter = emitter

    def log(self, step, data):

        payload = {
            "type": "debug",
            "step": step,
            "data": data
        }

        print("🧠 DEBUG:", payload)

        if self.emitter:
            self.emitter(payload)