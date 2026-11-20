class ToolMemory:

    def __init__(self):
        self.scores = {}

    def update_score(self, tool_name, success=True):

        if tool_name not in self.scores:
            self.scores[tool_name] = {"ok": 0, "fail": 0}

        if success:
            self.scores[tool_name]["ok"] += 1
        else:
            self.scores[tool_name]["fail"] += 1

    def get_best_tool(self, tools):

        best = "chat"
        best_score = -1

        for t in tools:

            s = self.scores.get(t, {"ok": 0, "fail": 0})
            score = s["ok"] - s["fail"]

            if score > best_score:
                best_score = score
                best = t

        return best