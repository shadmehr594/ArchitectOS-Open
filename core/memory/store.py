class MemoryStore:

    def __init__(self):
        self.cache = []

    def write(self, item):
        self.cache.append(item)

    def read(self):
        return self.cache