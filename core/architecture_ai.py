class ArchitectureAI:

    def apply_rules(self, spatial, rooms):

        suggestions = []

        for floor_id, floor in spatial.items():

            nodes = floor.get("nodes", {})

            # Rule 1: density check
            if len(nodes) < 8:
                suggestions.append({
                    "floor": floor_id,
                    "issue": "Low density layout",
                    "fix": "Add structural nodes"
                })

            # Rule 2: imbalance check
            xs = [n["x"] for n in nodes.values()]
            ys = [n["y"] for n in nodes.values()]

            if max(xs) - min(xs) > 50:
                suggestions.append({
                    "floor": floor_id,
                    "issue": "Over stretched layout",
                    "fix": "Compress horizontal span"
                })

        return suggestions