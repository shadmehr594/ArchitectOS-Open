class VoiceRouter:

    def __init__(self, registry):
        self.registry = registry

    def route(self, step):

        tool_name = step.get("tool", "chat")

        tool = self.registry.get(tool_name)

        return tool