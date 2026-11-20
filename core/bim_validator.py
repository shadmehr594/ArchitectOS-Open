class BIMValidator:

    def validate(self, design):

        errors = []


        if not design:
            return {
                "valid": False,
                "errors": [
                    "empty design"
                ],
                "floor_count": 0
            }


        if (
            isinstance(design, dict)
            and "nodes" in design
            and "connections" in design
        ):
            design = {
                "F1": design
            }


        for floor, data in design.items():

            # ignore metadata
            if floor == "metadata":
                continue

            if not isinstance(data, dict):
                errors.append(
                    f"{floor}: invalid floor data"
                )
                continue


            nodes = data.get("nodes", {})
            connections = data.get("connections", [])


            if len(nodes) < 3:
                errors.append(
                    f"{floor}: too few nodes"
                )


            if not connections:
                errors.append(
                    f"{floor}: no connections"
                )


            for conn in connections:
                if not isinstance(conn, (list, tuple)):
                    errors.append(
                        f"{floor}: invalid connection format"
                    )  
                    


        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "floor_count": len(design)
        }