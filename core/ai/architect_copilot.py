class ArchitectCopilot:

    def __init__(self, design_engine, zoning_engine=None):
        self.engine = design_engine
        self.zoning = zoning_engine

    # ======================
    # MAIN DESIGN ASSIST
    # ======================
    def suggest(self, state):

        base = self.engine.execute(state)

        suggestions = {
            "layout_improvements": self._analyze_layout(base),
            "zoning_warnings": self._check_zoning(base),
            "auto_fixes": self._auto_fix(base)
        }

        return {
            "base": base,
            "suggestions": suggestions
        }

    # ======================
    # ANALYZE SPATIAL
    # ======================
    def _analyze_layout(self, base):

        issues = []

        for floor, data in base["spatial"].items():

            if len(data["nodes"]) < 5:
                issues.append(f"{floor}: low spatial complexity")

            if len(data["nodes"]) > 20:
                issues.append(f"{floor}: overcrowded layout")

        return issues

    # ======================
    # ZONING CHECK
    # ======================
    def _check_zoning(self, base):

        if not self.zoning:
            return []

        return self.zoning.validate(
            site=base["site"],
            building_plan={
                "footprint": 60,
                "height": 3
            }
        )

    # ======================
    # AUTO FIX ENGINE
    # ======================
    def _auto_fix(self, base):

        fixes = []

        for floor, data in base["spatial"].items():

            if "F2" in floor:
                fixes.append({
                    "floor": floor,
                    "action": "suggest_expand_living_room"
                })

        return fixes