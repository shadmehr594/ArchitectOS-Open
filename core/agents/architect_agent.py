class ArchitectAgent:


    def __init__(
        self,
        llm
    ):

        self.llm = llm



    def build(
        self,
        plan
    ):


        prompt = """
You are a BIM architect AI.

Create building structure from this plan:

{plan}

Return JSON:

{
  "floors": {
    "F1": {
      "nodes": {},
      "connections": []
    }
  }
}
""".format(
            plan=plan
        )


        return self.llm.ask(
            prompt
        )