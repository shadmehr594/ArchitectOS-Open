from core.ai.optimization_memory_engine import OptimizationMemoryEngine
from core.ai.rule_memory_engine import RuleMemoryEngine


class OptimizationRuleMemoryEngine:


    def __init__(self):

        self.optimization_memory = OptimizationMemoryEngine()

        self.rule_memory = RuleMemoryEngine()

        self.rules = []



    # ==========================================
    # V96 COMPATIBILITY API
    # store(rule)
    # ==========================================
    def store(
        self,
        rule
    ):

        self.rules.append(
            rule
        )


        try:

            return self.rule_memory.store_rule(
                rule
            )

        except AttributeError:

            return {

                "status":
                "RULE_STORED",

                "count":
                len(
                    self.rules
                )

            }



    # ==========================================
    # LEGACY
    # ==========================================
    def store_rule(
        self,
        rule
    ):

        return self.store(
            rule
        )



    def get_rules(self):

        try:

            return self.rule_memory.get_rules()

        except AttributeError:

            return self.rules



    # ==========================================
    # V98 RECALL API
    # ==========================================
    def recall(
        self
    ):

        return {

            "engine":
            "ARCHITECTOS_OPTIMIZATION_RULE_MEMORY_ENGINE_V96",

            "rules":
            self.rules,

            "count":
            len(
                self.rules
            )

        }



    def store_optimization(
        self,
        data
    ):

        return self.optimization_memory.store(
            data
        )



    def get_optimizations(self):

        try:

            return self.optimization_memory.get_all()

        except AttributeError:

            return []



    def learn(
        self,
        feedback
    ):

        return {

            "status":
            "learned",

            "feedback":
            feedback

        }