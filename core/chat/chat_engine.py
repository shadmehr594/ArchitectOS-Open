class ChatArchitect:

    def __init__(self, design_engine, copilot=None, renderer=None):
        self.design = design_engine
        self.copilot = copilot
        self.renderer = renderer

    def handle(self, message):

        # STEP 1: DESIGN
        result = self.design.execute(message)

        response = {
            "design": result
        }

        # STEP 2: AI SUGGESTIONS
        if self.copilot:
            response["ai"] = self.copilot.suggest(message)

        # STEP 3: COMFY UI RENDER TRIGGER
        if self.renderer:
            response["render"] = self.renderer.generate_prompt(result)

        return response