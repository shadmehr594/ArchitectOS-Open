class BaseAgent:

    def __init__(self):
        self.memory = []

    def build(self, plan):
        return {
            "base": True,
            "plan": plan
        }