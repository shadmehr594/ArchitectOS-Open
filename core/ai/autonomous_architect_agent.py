class AutonomousArchitectAgent:

    def __init__(self, pipeline, reasoning_engine):

        self.pipeline = pipeline
        self.reasoning = reasoning_engine

    # ======================
    # MAIN ENTRY
    # ======================
    def run(self, state):

        # ======================
        # STEP 1 - GENERATE CANDIDATES
        # ======================
        candidates = self._generate_design_variants(state)

        evaluated = []

        # ======================
        # STEP 2 - EVALUATE EACH DESIGN
        # ======================
        for design in candidates:

            result = self.pipeline.run(
                site=design["site"],
                spatial=design["spatial"],
                grid=design["grid"]
            )

            analysis = self.reasoning.analyze(
                site=result["site"],
                zoning=result["zoning"],
                spatial=result["spatial"],
                structure=result.get("structure", {})
            )

            evaluated.append({
                "design": design,
                "result": result,
                "analysis": analysis
            })

        # ======================
        # STEP 3 - SELECT BEST DESIGN
        # ======================
        best = self._select_best(evaluated)

        # ======================
        # STEP 4 - SELF-IMPROVE LOOP
        # ======================
        if best["analysis"]["decision"]["status"] != "approved":

            improved = self._improve_design(best["design"])

            return self.run(improved)

        return {
            "status": "final",
            "best_design": best,
            "iterations": len(evaluated)
        }

    # ======================
    # DESIGN GENERATOR
    # ======================
    def _generate_design_variants(self, state):

        return [
            {
                "name": "compact",
                "site": self._mock_site("compact"),
                "spatial": self._mock_spatial(0.8),
                "grid": self._mock_grid(4)
            },
            {
                "name": "balanced",
                "site": self._mock_site("balanced"),
                "spatial": self._mock_spatial(1.0),
                "grid": self._mock_grid(5)
            },
            {
                "name": "luxury",
                "site": self._mock_site("luxury"),
                "spatial": self._mock_spatial(1.2),
                "grid": self._mock_grid(6)
            }
        ]

    # ======================
    # SELECTION LOGIC
    # ======================
    def _select_best(self, evaluated):

        return max(
            evaluated,
            key=lambda x: x["analysis"]["decision"]["confidence"]
        )

    # ======================
    # SELF IMPROVEMENT LOOP
    # ======================
    def _improve_design(self, design):

        # ساده شده: tweak grid + density
        design["grid"]["density"] = design["grid"].get("density", 1.0) * 0.9

        return design

    # ======================
    # MOCK HELPERS (replace later)
    # ======================
    def _mock_site(self, mode):
        return {"type": "rect", "mode": mode}

    def _mock_spatial(self, scale):
        return {"scale": scale}

    def _mock_grid(self, size):
        return {"columns": [{"x": i * size, "y": 0} for i in range(5)]}