class AdjacencyEngine:


    def __init__(self):

        print("🔗 Adjacency Engine v19.5 ACTIVE")


    def generate(self, zoning, plan):

        rules = []

        spaces = plan.get(
            "spaces",
            {}
        )


        # ==========================
        # RESIDENTIAL RULES
        # ==========================

        typical = spaces.get(
            "typical_floor",
            []
        )


        if "living" in typical and "kitchen" in typical:

            rules.append(
                {
                    "from": "living",
                    "to": "kitchen",
                    "relation": "adjacent",
                    "priority": "high"
                }
            )


        if "bedroom" in typical and "bathroom" in typical:

            rules.append(
                {
                    "from": "bedroom",
                    "to": "bathroom",
                    "relation": "near",
                    "priority": "medium"
                }
            )


        if "living" in typical:

            rules.append(
                {
                    "from": "living",
                    "to": "garden",
                    "relation": "visual_connection",
                    "priority": "high"
                }
            )


        # ==========================
        # NEGATIVE RULES
        # ==========================

        rules.append(
            {
                "from": "bedroom",
                "to": "parking",
                "relation": "avoid",
                "priority": "high"
            }
        )


        rules.append(
            {
                "from": "bathroom",
                "to": "entrance",
                "relation": "avoid_direct",
                "priority": "medium"
            }
        )


        return {

            "rules": rules,

            "count": len(rules),

            "strategy":
                "architectural_adjacency_reasoning",

            "version":
                "19.5"

        }