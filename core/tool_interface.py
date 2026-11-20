class BaseTool:
    name = "base"

    def execute(self, input_text: str):
        raise NotImplementedError("Tool must implement execute()")