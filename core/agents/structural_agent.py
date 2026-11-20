class StructuralAgent:

    def analyze(self, design):

        report = {}

        for floor, data in design.items():

            nodes = data.get("nodes", {})

            report[floor] = {
                "load_points": len(nodes),
                "stability": "ok" if len(nodes) >= 3 else "weak"
            }

        return report