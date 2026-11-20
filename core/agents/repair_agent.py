class RepairAgent:

    def fix(self, design, issues):

        for issue in issues:

            floor = issue["floor"]
            data = design[floor]

            if len(data["nodes"]) < 3:
                data["nodes"]["auto_room"] = {"type": "room"}

            if not data["connections"]:
                keys = list(data["nodes"].keys())
                if len(keys) >= 2:
                    data["connections"] = [[keys[0], keys[1]]]

        return design