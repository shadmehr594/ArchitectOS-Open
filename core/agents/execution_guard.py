# ==========================================================
# ArchitectOS Execution Guard v67.9
# Execution Permission Layer
# Supports ExecutionPlan Object
# ==========================================================


class ExecutionGuard:


    def __init__(self):

        print(
            "🛡️ Execution Guard v67.9 ACTIVE"
        )



    def check(
        self,
        plan
    ):


        if not plan:

            return {

                "status": "blocked",

                "reason":
                "No execution plan"

            }



        # Support ExecutionPlan object
        if hasattr(plan, "workflow"):

            workflow = plan.workflow

            plan_data = {

                "intent":
                    plan.intent,

                "workflow":
                    plan.workflow,

                "engine":
                    plan.engine

            }


        # Support dict
        elif isinstance(plan, dict):

            workflow = plan.get(
                "workflow"
            )

            plan_data = plan


        else:

            return {

                "status":
                    "blocked",

                "reason":
                    "Invalid plan format"

            }



        heavy_workflows = [

            "flux_img2img",
            "flux",
            "wan_i2v"

        ]



        if workflow in heavy_workflows:


            return {


                "status":
                    "waiting_confirmation",


                "message":
                    "Execution requires user confirmation",


                "plan":
                    plan_data

            }



        return {


            "status":
                "approved",


            "plan":
                plan_data

        }



execution_guard = ExecutionGuard()