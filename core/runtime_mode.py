class RuntimeMode:
    def __init__(self):
        self.mode = "hybrid"

    def set_mode(self, mode):
        self.mode = mode

    def is_online(self):
        return self.mode in ["online", "hybrid"]

    def is_offline(self):
        return self.mode in ["offline", "hybrid"]