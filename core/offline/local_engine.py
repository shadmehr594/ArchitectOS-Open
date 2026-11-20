class LocalBIMEngine:

    def __init__(self):
        self.cache = {}
        self.mode = "offline"

    def load(self, bim_data):
        self.cache = bim_data
        return self.cache

    def analyze(self):
        structure = self.cache.get("structure", {})
        return {
            "columns": len(structure.get("columns", [])),
            "beams": len(structure.get("beams", [])),
            "mode": "offline"
        }