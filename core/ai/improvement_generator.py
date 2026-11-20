# ==========================================================
# ArchitectOS Improvement Generator v76
# Visual Feedback -> Design Improvements
# ==========================================================


class ImprovementGenerator:


    def __init__(self):

        print(
            "⚙️ Improvement Generator v76 ACTIVE"
        )



    # ======================================================
    # GENERATE IMPROVEMENT PLAN
    # ======================================================

    def generate(
        self,
        visual_review
    ):


        print(
            "⚙️ GENERATING IMPROVEMENT PLAN"
        )



        improvements = []



        score = visual_review.get(
            "quality_score",
            0
        )


        architecture = visual_review.get(
            "architectural_review",
            {}
        )



        if score < 0.9:


            improvements.append(

                "increase architectural realism"

            )


        if architecture.get(
            "materials"
        ) == "consistent":


            improvements.append(

                "enhance facade material details"

            )


        if architecture.get(
            "composition"
        ) == "balanced":


            improvements.append(

                "improve lighting and environment"

            )



        plan = {


            "status":
                "generated",


            "quality_before":
                score,


            "improvements":
                improvements,


            "next_action":
                "refine_prompt"


        }



        print(
            "✅ IMPROVEMENT PLAN READY"
        )



        return plan





improvement_generator = ImprovementGenerator()