class IntentClassifier:

    def __init__(self, llm):
        self.llm = llm

    def classify(self, text):

        prompt = f"""
Classify voice command:

TEXT:
{text}

Return JSON:
{
 "intents": ["bim", "image", "chat"],
 "confidence": 0-1
}
"""

        return self.llm.ask(prompt)