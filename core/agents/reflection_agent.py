class ReflectionAgent:

    def analyze(self, plan, design, validation, graph):

        score = 100

        if validation.get("errors"):
            score -= len(validation["errors"]) * 10

        if len(graph.get("edges", [])) == 0:
            score -= 30

        return {
            "quality_score": max(score, 0),
            "suggestion": "increase structural redundancy",
            "next_improvement": "add circulation optimization layer"
        }