# ==================================================
# ArchitectOS Autonomous Agent v63
# ==================================================


class AutonomousAgentEngine:


    VERSION = "architectos_agent_v63.0"



    def __init__(self):

        print(
            "🤖 ArchitectOS Autonomous Agent v63.0 ACTIVE"
        )



    def build(
        self,
        graph
    ):


        decision = graph.get(
            "decision",
            {}
        )


        experience = graph.get(
            "memory",
            {}
        )


        tasks = []



        # ------------------------------------------
        # Extract decision confidence safely
        # ------------------------------------------

        confidence = 0

        if decision.get("decisions"):

            confidence = decision["decisions"][0].get(
                "confidence",
                0
            )



        best_action = decision.get(
            "best_decision"
        )



        # ------------------------------------------
        # Decision execution
        # ------------------------------------------

        if best_action:


            tasks.append(

                {
                    "task":
                    "apply_best_decision",


                    "action":
                    best_action,


                    "confidence":
                    confidence
                }

            )



        # ------------------------------------------
        # Experience reuse
        # ------------------------------------------

        if experience:


            tasks.append(

                {
                    "task":
                    "reuse_previous_learning",


                    "action":
                    "apply_experience_patterns"
                }

            )



        return {


            "engine":
            self.VERSION,


            "agent":
            {

                "status":
                "autonomous",


                "tasks":
                tasks

            },


            "tasks_generated":
            len(tasks)

        }