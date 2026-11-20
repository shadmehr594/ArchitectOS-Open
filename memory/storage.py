class MemoryStorage:
    def __init__(self):
        self.data = []

    def save(self, item):
        self.data.append(item)

    def search(self, query, limit=5):
        # fake simple search (فعلاً)
        return self.data[-limit:] if self.data else []

    def load_recent(self, limit=5):
        return self.data[-limit:]