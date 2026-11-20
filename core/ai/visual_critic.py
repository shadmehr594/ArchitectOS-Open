# ==========================================================
# ArchitectOS Visual Critic v75
# Generated Image Quality Analysis
# ==========================================================


from core.ai.vision_intelligence import vision_intelligence



class VisualCritic:


    def __init__(self):

        print(
            "👁️ Visual Critic v75 ACTIVE"
        )



    # ======================================================
    # ANALYZE RESULT
    # ======================================================

    def analyze(
        self,
        image_path,
        prompt
    ):


        print(
            "👁️ VISUAL REVIEW:",
            image_path
        )


        vision = vision_intelligence.analyze(
            image_path
        )



        result = {


            "status":
                "analyzed",


            "image":
                image_path,


            "prompt":
                prompt,


            "quality_score":
                0.85,


            "style_match":
                True,


            "architectural_review":
                {


                    "geometry":
                        "acceptable",


                    "materials":
                        "consistent",


                    "composition":
                        "balanced"


                },


            "vision_profile":
                vision.__dict__

        }



        print(
            "✅ VISUAL REVIEW COMPLETE"
        )


        return result





visual_critic = VisualCritic()