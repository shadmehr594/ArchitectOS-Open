class DesignLoopEngine:

    def __init__(self, max_iterations=3):

        self.max_iterations = max_iterations

    # ======================
    # MAIN LOOP
    # ======================
    def run(self, context, agents):

        state = context
        history = []

        for i in range(self.max_iterations):

            print(f"🔁 ITERATION {i+1}")

            # ======================
            # 1. DESIGN PHASE
            # ======================
            design = agents["architect"].run(state)

            state["bim"] = design

            # ======================
            # 2. STRUCTURE PHASE
            # ======================
            structure = agents["structural"].run(state)

            state["structure"] = structure

            # ======================
            # 3. ANALYSIS PHASE
            # ======================
            analysis = agents["analyst"].run(state)

            state["analysis"] = analysis

            history.append({
                "iteration": i + 1,
                "design": design,
                "structure": structure,
                "analysis": analysis
            })

            # ======================
            # 4. STOP CONDITION
            # ======================
            if self._is_good_enough(analysis):
                print("✅ DESIGN ACCEPTED")
                break

            # ======================
            # 5. FEEDBACK LOOP
            # ======================
            state = self._apply_feedback(state, analysis)

        return {
            "final_state": state,
            "history": history
        }

    # ======================
    # QUALITY CHECK
    # ======================
    def _is_good_enough(self, analysis):

        issues = analysis.get("issues", [])

        risk = analysis.get("risk_level", "low")

        if len(issues) == 0 and risk == "low":
            return True

        return False

    # ======================
    # FEEDBACK ENGINE
    # ======================
    def _apply_feedback(self, state, analysis):

        issues = analysis.get("issues", [])

        # ساده‌سازی اصلاح خودکار

        for issue in issues:

            if "Overload column" in issue:
                state["fix"] = "increase_columns"

            if "Overload beam" in issue:
                state["fix"] = "reduce_span"

            if "Bad proportions" in issue:
                state["fix"] = "resize_rooms"

        return state