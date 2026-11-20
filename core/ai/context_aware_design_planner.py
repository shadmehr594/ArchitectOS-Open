class ContextAwareDesignPlanner:


    def __init__(self):

        print(
            "🧭 Context Aware Design Planner v26.7 ACTIVE"
        )



    def plan(
        self,
        context,
        memory_result=None
    ):


        strategy = "balanced_design"


        confidence = 0.5


        priorities = []



        climate = context.get(
            "climate"
        )


        green_roof = context.get(
            "green_roof",
            False
        )


        site = context.get(
            "site"
        )


        floors = context.get(
            "floors"
        )



        # -------------------------
        # Memory influence
        # -------------------------

        if memory_result:


            recommendation = memory_result.get(
                "recommendation"
            )


            if recommendation:


                strategy = recommendation.get(
                    "strategy",
                    strategy
                )


                confidence = recommendation.get(
                    "confidence",
                    confidence
                )



        # -------------------------
        # Climate logic
        # -------------------------

        if climate in [

            "hot",

            "warm"

        ]:


            priorities.append(
                "solar_control"
            )


            priorities.append(
                "thermal_envelope"
            )


        elif climate == "cold":


            priorities.append(
                "insulation"
            )



        # -------------------------
        # Roof logic
        # -------------------------

        if green_roof:


            priorities.append(
                "green_roof_integration"
            )



        # -------------------------
        # Site logic
        # -------------------------

        if site:


            priorities.append(
                "site_optimization"
            )


        if floors:


            priorities.append(
                "vertical_space_planning"
            )



        return {


            "engine":
            "context_design_planner_v26.7",


            "status":
            "planned",


            "context":
            {

                "site": site,

                "floors": floors,

                "climate": climate

            },


            "recommended_strategy":
            strategy,


            "design_priorities":
            priorities,


            "confidence":
            confidence

        }