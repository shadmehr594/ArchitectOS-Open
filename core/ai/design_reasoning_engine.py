class DesignReasoningEngine:

    def __init__(self):
        pass

    # ======================
    # MAIN REASONING PIPELINE
    # ======================
    def analyze(self, site, zoning, spatial, structure):

        issues = []
        suggestions = []

        # ======================
        # 1. ZONING CHECK
        # ======================
        if not zoning.get("valid", True):
            issues.extend(zoning.get("violations", []))
            suggestions.append("Reduce footprint or adjust massing")

        # ======================
        # 2. COVERAGE ANALYSIS
        # ======================
        coverage = zoning.get("coverage", 0)

        if coverage > 0.6:
            suggestions.append("Reduce building footprint to meet zoning limit")

        # ======================
        # 3. SPATIAL QUALITY CHECK
        # ======================
        spatial_score = self._evaluate_spatial(spatial)

        if spatial_score < 0.5:
            suggestions.append("Improve circulation efficiency")

        # ======================
        # 4. STRUCTURAL LOGIC CHECK
        # ======================
        structure_score = self._evaluate_structure(structure)

        if structure_score < 0.6:
            suggestions.append("Optimize column grid alignment")

        # ======================
        # FINAL DECISION ENGINE
        # ======================
        decision = self._make_decision(
            issues,
            suggestions,
            coverage,
            spatial_score,
            structure_score
        )

        return {
            "issues": issues,
            "suggestions": suggestions,
            "scores": {
                "coverage": coverage,
                "spatial": spatial_score,
                "structure": structure_score
            },
            "decision": decision
        }

    # ======================
    # SPATIAL SCORING
    # ======================
    def _evaluate_spatial(self, spatial):

        if not spatial:
            return 0.3

        total_nodes = 0
        valid_nodes = 0

        for floor, data in spatial.items():

            for node, props in data.get("nodes", {}).items():

                total_nodes += 1

                if props.get("w", 0) > 0 and props.get("h", 0) > 0:
                    valid_nodes += 1

        return valid_nodes / total_nodes if total_nodes else 0

    # ======================
    # STRUCTURE SCORING
    # ======================
    def _evaluate_structure(self, structure):

        if not structure:
            return 0.4

        beams = len(structure.get("beams", []))
        columns = len(structure.get("columns", []))

        if columns == 0:
            return 0

        ratio = beams / columns

        # heuristic optimal range
        if 1.5 <= ratio <= 3.5:
            return 0.9
        elif 1.0 <= ratio < 4.5:
            return 0.7
        else:
            return 0.4

    # ======================
    # DECISION ENGINE
    # ======================
    def _make_decision(self, issues, suggestions, coverage, spatial_score, structure_score):

        score = (1 - coverage) + spatial_score + structure_score

        if issues:
            return {
                "status": "needs_revision",
                "confidence": min(score / 3, 1.0)
            }

        if score > 2.2:
            return {
                "status": "approved",
                "confidence": 0.9
            }

        return {
            "status": "acceptable",
            "confidence": 0.6
        }