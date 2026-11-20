class BIMState:

    def __init__(self):

        self.data = {
            "site": None,
            "bim": None,
            "structure": None,
            "analysis": None,
            "render": None
        }

    def update(self, key, value):
        self.data[key] = value

    def get(self, key=None):

        if key:
            return self.data.get(key)

        return self.data