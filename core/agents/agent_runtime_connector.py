# ==========================================================
# ArchitectOS Agent Runtime Connector v68.5
# Approved Execution Path
# ==========================================================


from core.agents.execution_guard import execution_guard
from core.cognition.runtime_dispatcher import runtime_dispatcher



class AgentRuntimeConnector:


    def __init__(self):

        print(
            "🔌 Agent Runtime Connector v68.5 ACTIVE"
        )



    # ======================================================
    # PREPARE
    # ======================================================

    def prepare(
        self,
        plan,
        prompt
    ):


        permission = execution_guard.check(
            plan
        )


        if permission["status"] != "approved":


            return permission



        return {


            "status":
                "ready",


            "plan":
                plan,


            "prompt":
                prompt

        }



    # ======================================================
    # EXECUTE AFTER APPROVAL
    # ======================================================

    def execute(
        self,
        plan,
        prompt,
        approved=False
    ):


        # -----------------------------------------------
        # If not approved, check permission
        # -----------------------------------------------

        if not approved:


            permission = execution_guard.check(
                plan
            )


            if permission["status"] != "approved":


                return permission



        # -----------------------------------------------
        # Runtime execution
        # -----------------------------------------------

        result = runtime_dispatcher.dispatch(

            plan,

            prompt

        )


        return result





agent_runtime_connector = AgentRuntimeConnector()