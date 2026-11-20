class SelfHealingCore:

    def __init__(self, registry, brain):
        self.registry = registry
        self.brain = brain

    def tick(self, error_log):

        fixes = []

        for error in error_log:

            if "BaseAgent is not defined" in error:
                fixes.append({"action": "inject_base_agent"})

            if "f-string" in error:
                fixes.append({"action": "fix_fstring"})

        return fixes