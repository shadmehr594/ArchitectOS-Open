class Fixer:

    def fix(self, design):

        for floor in design:

            if "nodes" not in design[floor]:
                design[floor]["nodes"] = {}

            if "connections" not in design[floor]:
                design[floor]["connections"] = []

        return design