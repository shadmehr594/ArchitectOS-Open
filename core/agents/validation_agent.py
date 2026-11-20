class ValidationAgent:

    def validate(self, design):

        errors = []

        for floor, data in design.items():

            if len(data["nodes"]) < 2:
                errors.append(f"{floor}: too few nodes")

            if not data["connections"]:
                errors.append(f"{floor}: missing connections")

        return {
            "valid": len(errors) == 0,
            "errors": errors
        }