# ==========================================================
# ArchitectOS Planner Engine v67.8
# Intent -> Execution Plan
# Smart Chat / Tool / GOD CORE Routing
# ==========================================================


from core.cognition.execution_plan import ExecutionPlan



WORKFLOW_MAP = {


    # ======================================================
    # IMAGE
    # ======================================================

    "facade_edit": {
        "workflow": "flux_img2img",
        "engine": "flux"
    },


    "image_generation": {
        "workflow": "flux",
        "engine": "flux"
    },


    "image_edit": {
        "workflow": "flux_img2img",
        "engine": "flux"
    },


    "video_generation": {
        "workflow": "wan_i2v",
        "engine": "wan"
    },


    "material_change": {
        "workflow": "flux_img2img",
        "engine": "flux"
    },


    "lighting_change": {
        "workflow": "flux_img2img",
        "engine": "flux"
    },



    # ======================================================
    # DESIGN FAMILY
    # ======================================================


    "design_request": {

        "workflow": "god_core",

        "engine": "god_core",

        "building_type": "generic"

    },


    "villa_design": {

        "workflow": "god_core",

        "engine": "god_core",

        "building_type": "villa"

    },


    "apartment_design": {

        "workflow": "god_core",

        "engine": "god_core",

        "building_type": "apartment"

    },


    "highrise_design": {

        "workflow": "god_core",

        "engine": "god_core",

        "building_type": "tower"

    },



    # ======================================================
    # CHAT
    # ======================================================


    "chat": {

        "workflow": "none",

        "engine": "chat"

    },


    "greeting": {

        "workflow": "none",

        "engine": "chat"

    },


    "small_talk": {

        "workflow": "none",

        "engine": "chat"

    },


    "memory_query": {

        "workflow": "none",

        "engine": "memory"

    }

}





class PlannerEngine:


    def __init__(self):

        print(
            "📐 Planner Engine v67.8 ACTIVE"
        )



    def create_plan(
        self,
        intent_result
    ):


        intent = getattr(

            intent_result,

            "intent",

            "unknown"

        )


        config = WORKFLOW_MAP.get(

            intent

        )



        if not config:


            return ExecutionPlan(

                intent=intent,

                workflow="none",

                engine="chat"

            )



        plan = ExecutionPlan(

            intent=intent,

            workflow=config["workflow"],

            engine=config["engine"]

        )


        # attach metadata if supported

        if hasattr(
            plan,
            "metadata"
        ):

            plan.metadata = {

                "building_type":
                    config.get(
                        "building_type",
                        "generic"
                    )

            }


        return plan





planner = PlannerEngine()