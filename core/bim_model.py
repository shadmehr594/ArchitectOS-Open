class BIMModel:
    def __init__(self):
        self.data = {}

    def update(self, key, value):
        self.data[key] = value

    def export(self):
        return self.data