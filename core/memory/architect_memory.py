class ArchitectMemory:

    def __init__(self):

        self.memory = []

    # ======================
    # STORE EXPERIENCE
    # ======================
    def store(self, project, analysis):

        self.memory.append({
            "project": project,
            "score": analysis.get("score", 0),
            "issues": analysis.get("issues", []),
            "timestamp": self._now()
        })

    # ======================
    # RETRIEVE SIMILAR CASES
    # ======================
    def retrieve_best(self):

        return sorted(
            self.memory,
            key=lambda x: x["score"],
            reverse=True
        )[:5]

    # ======================
    # FAILURE PATTERNS
    # ======================
    def failures(self):

        return [
            m for m in self.memory
            if m["score"] < 60
        ]

    def _now(self):

        import time
        return time.time()