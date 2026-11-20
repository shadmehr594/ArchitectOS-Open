# ==========================================================
# ArchitectOS Runtime Manager v2
# Runtime Orchestration Layer
# Permission -> Confirmation -> Dispatch -> Execution
# ==========================================================


from core.agents.execution_guard import execution_guard
from core.agents.confirmation_handler import confirmation_handler
from core.agents.agent_runtime_connector import agent_runtime_connector



class RuntimeManager:


    def __init__(self):

        print(
            "⚙️ Runtime Manager v2 ACTIVE"
        )



    # ======================================================
    # EXECUTE
    # ======================================================

    def execute(
        self,
        plan,
        message
    ):


        print(
            "⚙️ RUNTIME START"
        )


        # ------------------------------
        # Validate
        # ------------------------------

        if plan is None:

            return {

                "status":
                    "error",

                "message":
                    "No execution plan."

            }



        # ------------------------------
        # Permission Layer
        # ------------------------------

        permission = execution_guard.check(
            plan
        )



        if (
            permission.get("status")
            ==
            "waiting_confirmation"
        ):


            return confirmation_handler.store(
                plan,
                message
            )



        # ------------------------------
        # Dispatch Layer
        # ------------------------------

        result = self.dispatch(
            plan,
            message
        )


        return self.format_result(
            result
        )



    # ======================================================
    # DISPATCH
    # ======================================================

    def dispatch(
        self,
        plan,
        message
    ):


        return agent_runtime_connector.execute(

            plan,

            message

        )



    # ======================================================
    # RESULT FORMAT
    # ======================================================

    def format_result(
        self,
        result
    ):


        if isinstance(
            result,
            dict
        ):

            return result



        return {

            "status":
                "success",

            "result":
                result

        }



    # ======================================================
    # CONFIRM
    # ======================================================

    def confirm(
        self,
        message
    ):


        approval = confirmation_handler.confirm(
            message
        )



        if (
            approval.get("status")
            !=
            "approved"
        ):


            return approval



        result = agent_runtime_connector.execute(

            approval["plan"],

            approval["prompt"],

            approved=True

        )


        return self.format_result(
            result
        )




# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


runtime_manager = RuntimeManager()