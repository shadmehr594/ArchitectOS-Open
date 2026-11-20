# ==========================================================
# ArchitectOS Design Approval Gate v1.0
#
# BIM Preview -> Human Approval -> Render Permission
#
# Purpose:
# - Stop render until design approval
# - Preserve BIM review state
# - No render execution
# ==========================================================


class DesignApprovalGate:


    VERSION = "1.0"



    def __init__(self):

        print(
            "✅ DESIGN APPROVAL GATE v1.0 ONLINE"
        )



    # ======================================================
    # REQUEST REVIEW
    # ======================================================

    def request_review(
        self,
        bim_preview
    ):

        return {

            "approval_status":
                "waiting_for_approval",


            "approved":
                False,


            "preview":
                bim_preview,


            "metadata":
            {

                "engine":
                    "DesignApprovalGate",


                "version":
                    self.VERSION

            }

        }



    # ======================================================
    # APPROVE DESIGN
    # ======================================================

    def approve(
        self,
        review_context
    ):


        review_context = review_context or {}



        review_context["approved"] = True


        review_context["approval_status"] = (
            "approved"
        )



        return review_context



    # ======================================================
    # CHECK APPROVAL
    # ======================================================

    def can_render(
        self,
        review_context
    ):


        if not review_context:

            return False



        return (
            review_context.get(
                "approved",
                False
            )
            is True
        )