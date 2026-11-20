class ConstraintAgent:

    def check(self, design):

        issues = []


        # ==========================================
        # NORMALIZE SINGLE FLOOR GRAPH
        # ==========================================

        if (
            isinstance(design, dict)
            and "nodes" in design
            and "connections" in design
        ):
            design = {
                "F1": design
            }


        # ==========================================
        # CHECK FLOORS
        # ==========================================

        for floor, data in design.items():

            if not isinstance(data, dict):
                issues.append({
                    "floor": floor,
                    "error": "invalid floor data"
                })
                continue


            nodes = data.get("nodes", {})
            connections = data.get("connections", [])


            if len(nodes) < 3:
                issues.append({
                    "floor": floor,
                    "error": "too few nodes"
                })


            if not connections:
                issues.append({
                    "floor": floor,
                    "error": "no connections"
                })


        return issues