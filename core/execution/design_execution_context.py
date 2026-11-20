# ==========================================================
# ArchitectOS Design Execution Context v1.1
#
# Planning + BIM + Approval Context
#
# Purpose:
# - Carry approved design into execution
# - Connect BIM review to render pipeline
# - Prevent unapproved execution
# ==========================================================


class DesignExecutionContext:


    VERSION = "1.1"



    def __init__(
        self,
        execution_context
    ):

        print(
            "🚀 DESIGN EXECUTION CONTEXT v1.1 ONLINE"
        )

        self.execution_context = (
            execution_context
            if isinstance(
                execution_context,
                dict
            )
            else {}
        )



    # ======================================================
    # PLAN
    # ======================================================

    def get_plan(
        self
    ):

        return self.execution_context.get(
            "planning",
            {}
        ).get(
            "selected"
        )



    # ======================================================
    # BIM
    # ======================================================

    def get_bim(
        self
    ):

        return self.execution_context.get(
            "bim"
        )



    # ======================================================
    # APPROVAL
    # ======================================================

    def get_approval(
        self
    ):

        return self.execution_context.get(
            "approval"
        )



    def can_execute(
        self
    ):

        approval = self.get_approval()


        if not isinstance(
            approval,
            dict
        ):

            return False


        return (
            approval.get(
                "approved",
                False
            )
            is True
        )



    # ======================================================
    # EXPORT
    # ======================================================

    def export(
        self
    ):

        return {


            "design":

                self.get_plan(),



            "bim":

                self.get_bim(),



            "approval":

                self.get_approval(),



            "can_execute":

                self.can_execute(),



            "metadata":

            {

                "engine":
                    "DesignExecutionContext",


                "version":
                    self.VERSION

            }

        }