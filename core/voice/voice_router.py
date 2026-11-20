class VoiceRouter:

    def __init__(self, registry, brain):
        self.registry = registry
        self.brain = brain

    def route(self, text):

        t = text.lower()

        # 🏗 BIM
        if "house" in t or "building" in t:
            return self.registry.get("bim").execute(text)

        # 🎨 IMAGE
        if "draw" in t or "image" in t:
            return self.registry.get("image").execute(text)

        # 🧠 fallback LLM brain
        return self.brain.run(text)