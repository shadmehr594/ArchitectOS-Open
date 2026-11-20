class DesignScorer:

    def score(self, design, validation, issues):

        total_nodes = 0
        total_connections = 0


        for name, floor in design.items():

            # فقط بخش‌های فضایی را امتیاز بده
            if not isinstance(floor, dict):
                continue

            if "nodes" not in floor:
                continue


            total_nodes += len(
                floor.get("nodes", {})
            )

            total_connections += len(
                floor.get("connections", [])
            )


        score = 0


        # spatial quality
        score += min(total_nodes / 10, 1.0) * 0.5

        # connectivity
        score += min(total_connections / 10, 1.0) * 0.3


        # validation
        if not validation.get("errors"):
            score += 0.2


        # penalty
        if issues:
            score -= min(len(issues) * 0.05, 0.2)


        return round(score, 3)