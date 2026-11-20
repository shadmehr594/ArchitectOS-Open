class Architect:

    def build(self, plan, tool=None):

        floors = plan["floors"]

        design = {}

        for f in range(1, floors + 1):

            design[f"F{f}"] = {
                "nodes": self._nodes(f),
                "connections": self._connections(f)
            }

        return design

    def _nodes(self, floor):

        return {
            f"kitchen_{floor}": {"type": "kitchen"},
            f"living_{floor}": {"type": "living"},
            f"bath_{floor}": {"type": "bathroom"},
        }

    def _connections(self, floor):

        return [
            (f"kitchen_{floor}", f"living_{floor}"),
            (f"living_{floor}", f"bath_{floor}")
        ]