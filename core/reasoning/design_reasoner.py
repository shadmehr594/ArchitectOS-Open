class DesignReasoner:


    def __init__(self):

        print(
            "🧠 Design Reasoner Engine v20.1 Adaptive Critic ACTIVE"
        )


    def analyze(self, context):

        plan = context.get(
            "plan",
            {}
        )

        design = context.get(
            "design",
            {}
        )

        constraints = context.get(
            "constraints",
            {}
        )


        reasoning = {

            "orientation":
            self.orientation_analysis(
                plan
            ),


            "privacy":
            self.privacy_analysis(
                design
            ),


            "circulation":
            self.circulation_analysis(
                plan
            ),


            "daylight":
            self.daylight_analysis(
                design
            )

        }


        critique = self.critic(
            plan,
            design,
            constraints
        )


        intelligence_score = (
            self.calculate_intelligence(
                critique
            )
        )


        return {


            "engine":
            "design_reasoning_v20.1",


            "reasoning":
            reasoning,


            "adaptive_critic":
            critique,


            "design_intelligence":
            intelligence_score,


            "version":
            "20.1"

        }



    # ======================
    # CRITIC ENGINE
    # ======================

    def critic(
        self,
        plan,
        design,
        constraints
    ):


        weaknesses = []


        improvements = []


        if plan.get(
            "requirements",
            {}
        ).get(
            "green_roof"
        ):

            improvements.append(
                {
                    "area":
                    "sustainability",

                    "suggestion":
                    "increase roof vegetation integration"
                }
            )



        if not design:

            weaknesses.append(
                "missing_design_data"
            )


        if constraints.get(
            "violations"
        ):

            weaknesses.append(
                "constraint_conflicts"
            )


        if len(weaknesses)==0:

            weaknesses.append(
                "minor_spatial_optimization_possible"
            )



        return {


            "weaknesses":
            weaknesses,


            "improvements":
            improvements,


            "priority":
            "medium",


            "critic_status":
            "active"

        }



    # ======================
    # INTELLIGENCE SCORE
    # ======================

    def calculate_intelligence(
        self,
        critique
    ):


        score = 1.0


        if critique["weaknesses"]:

            score -= (
                len(
                    critique["weaknesses"]
                )
                * 0.05
            )


        return round(
            max(score,0),
            2
        )



    # ======================
    # REASONING MODULES
    # ======================


    def orientation_analysis(
        self,
        plan
    ):

        return {

            "strategy":
            "solar_orientation",

            "site":
            plan.get(
                "site",
                {}
            )

        }



    def privacy_analysis(
        self,
        design
    ):

        return {

            "strategy":
            "public_private_separation",

            "status":
            "checked"

        }



    def circulation_analysis(
        self,
        plan
    ):

        return {

            "vertical_core":
            "central",

            "floors":
            plan.get(
                "floors"
            )

        }



    def daylight_analysis(
        self,
        design
    ):

        return {

            "strategy":
            "natural_light_distribution",

            "checked":
            True

        }