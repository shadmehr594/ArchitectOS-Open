class ChatTool:
    def __init__(self, llm, memory):
        self.llm = llm
        self.memory = memory

    def execute(self, text):

        context = self.memory.search(text)
        context_text = "\n".join([c["output"] for c in context])

        prompt = f"""
User input: {text}

Memory:
{context_text}
"""

        output = self.llm.generate(prompt)

        self.memory.save(text, output)

        return {
            "output": output
        }


class MemoryTool:
    def __init__(self, memory):
        self.memory = memory

    def execute(self, text):
        self.memory.save(text, "saved")
        return {"output": "memory saved"}