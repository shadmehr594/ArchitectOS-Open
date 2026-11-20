class ManagerAgent:

    def __init__(self, agents):
        self.agents = agents

    def execute(self, context):

        results = {}

        for name, agent in self.agents.items():
            results[name] = agent.run(context)

        return self._merge(results)

    def _merge(self, results):

        return {
            "architect": results.get("architect"),
            "structure": results.get("structural"),
            "analysis": results.get("analyst"),
            "render": results.get("render")
        }