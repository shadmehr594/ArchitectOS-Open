class AnalystAgent(BaseAgent):

    def run(self, context):

        loads = context["loads"]

        issues = []

        for col in loads.get("columns", []):
            if col["axial_load_kN"] > 250:
                issues.append("Overload column")

        return {
            "issues": issues,
            "risk_level": "high" if issues else "low"
        }