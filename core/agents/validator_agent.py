class ValidatorAgent:

    def __init__(self, llm):
        self.llm = llm

    def validate(self, design):

        prompt = f"""
You are a BIM validator.

Check design errors:

{design}

Return JSON:
{
  "errors": [],
  "score": 0-100
}
"""

        return self.llm.ask(prompt)