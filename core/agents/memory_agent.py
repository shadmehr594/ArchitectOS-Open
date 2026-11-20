class MemoryAgent:

    def __init__(self):
        self.store = []

    def write(self, data):
        self.store.append(data)

    def read(self, intent):
        return [
            m for m in self.store
            if m.get("intent") == intent
        ]