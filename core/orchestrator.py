class ArchitectOSCore:
    def __init__(self, engines):
        self.engines = engines

    def run(self, input_data):
        state = {}

        print(
            "\n====== ORCHESTRATOR INPUT DEBUG ======"
        )

        print(
            type(input_data)
        )

        print(
            input_data
        )

        print(
            "======================================"
        )

        state = self.engines["design"].execute(state, input_data)
        state = self.engines["structure"].run(state)
        state = self.engines["analysis"].analyze(state)

        state = self.engines["ifc"].export(state)
        state = self.engines["export"].export(state)

        return state