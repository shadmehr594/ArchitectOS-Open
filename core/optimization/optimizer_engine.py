class OptimizationEngine:

    def __init__(self):
        self.modules = []


    def register(self, module):
        self.modules.append(module)


    def optimize(self, model):

        report = {

            "engine":
            "ARCHITECTOS_OPTIMIZATION_ENGINE_V86",

            "status":
            "OPTIMIZATION_STARTED",

            "changes":[]

        }


        for module in self.modules:

            result = module.optimize(model)

            report["changes"].append(result)


        report["status"] = "OPTIMIZATION_COMPLETED"


        return report