class RenderAgent(BaseAgent):

    def run(self, context):

        bim = context["bim"]

        return {
            "prompt": "ultra realistic architectural render, cinematic light, BIM accurate",
            "ready": True,
            "source": bim
        }