class ToolReasoner:

    def __init__(self, llm, registry):
        self.llm = llm
        self.registry = registry

    def choose_tool(self, plan):

        tools = list(self.registry.tools.keys())

        prompt = f"""
Choose best tool:

Plan:
{plan}

Available tools:
{tools}

Return only tool name.
"""

        return self.llm.ask(prompt)