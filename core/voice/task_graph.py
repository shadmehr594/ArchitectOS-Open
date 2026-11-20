class TaskGraph:

    def build(self, plan):

        nodes = []

        for step in plan.get("steps", []):

            nodes.append({
                "tool": step.get("tool"),
                "input": step.get("task"),
                "status": "pending"
            })

        return nodes