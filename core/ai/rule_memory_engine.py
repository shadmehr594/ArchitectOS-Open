class RuleMemoryEngine:


    def __init__(self):

        self.rules = []


    def store(self, rule):

        self.rules.append(rule)

        return {

            "engine":
            "ARCHITECTOS_RULE_MEMORY_ENGINE_V96",

            "status":
            "RULE_STORED",

            "rule_count":
            len(self.rules),

            "rule":
            rule

        }


    def recall(self):

        return {

            "engine":
            "ARCHITECTOS_RULE_MEMORY_ENGINE_V96",

            "rules":
            self.rules,

            "count":
            len(self.rules)

        }


    def find(self, pattern):

        results = []


        for rule in self.rules:

            if rule.get("pattern") == pattern:

                results.append(rule)


        return {

            "engine":
            "ARCHITECTOS_RULE_MEMORY_ENGINE_V96",

            "matches":
            results,

            "count":
            len(results)

        }