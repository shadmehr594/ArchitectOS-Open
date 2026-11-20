class RegistryRepair:

    def fix_missing_base(self, registry):

        if "BaseAgent" not in registry:

            from core.agents.base_agent import BaseAgent

            registry["BaseAgent"] = BaseAgent

        return registry