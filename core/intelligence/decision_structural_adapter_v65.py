"""
ArchitectOS BIM
Decision Structural Adapter v65

Purpose:
- Connect Structural Decision Bridge v65
  to Decision Intelligence v62
- Convert structural actions into global AI decisions
"""


class DecisionStructuralAdapter:

    VERSION = "65.0"


    def __init__(self):

        print(
            "🔗 Decision Structural Adapter v65.0 ACTIVE"
        )



    def adapt(
        self,
        structural_bridge_output
    ):


        actions = structural_bridge_output.get(
            "actions",
            []
        )


        priority_actions = structural_bridge_output.get(
            "priority_actions",
            []
        )


        decisions = []


        for action in actions:


            decisions.append({

                "source":
                "structural_intelligence",


                "domain":
                action.get("domain"),


                "target":
                action.get("target"),


                "decision":
                action.get("decision"),


                "action":
                action.get("recommended_action")

            })



        priorities = []


        for item in priority_actions:


            priorities.append({

                "target":
                item.get("target"),


                "priority":
                item.get("level"),


                "required_action":
                item.get("action")

            })



        return {


            "engine":
            f"decision_structural_adapter_v{self.VERSION}",


            "status":
            "completed",


            "decisions":
            decisions,


            "priorities":
            priorities,


            "statistics":{

                "decisions":
                len(decisions),

                "priorities":
                len(priorities)

            }

        }