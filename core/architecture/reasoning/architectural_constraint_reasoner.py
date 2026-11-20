class ArchitecturalConstraintReasoner:


    VERSION = "1.0"



    def __init__(self):

        print(
            "⚖️ ARCHITECTURAL CONSTRAINT REASONER v1.0 ONLINE"
        )



    def analyze(
        self,
        intent,
        site_analysis,
        selected_alternative
    ):


        constraints = []

        freedoms = []

        rules = []



        site = intent.get(
            "site",
            {}
        )


        neighbors = site.get(
            "neighbors",
            {}
        )


        climate = site.get(
            "climate",
            {}
        )


        requirements = intent.get(
            "requirements",
            []
        )



        # ==================================
        # PRIVACY
        # ==================================

        if (
            neighbors.get("east")
            or
            neighbors.get("west")
        ):


            constraints.append(
                "building should consider neighbor privacy"
            )


            rules.append(
                "private spaces should avoid uncontrolled exposure"
            )



        # ==================================
        # CLIMATE
        # ==================================

        if climate:


            constraints.append(
                "building should respond to climate conditions"
            )


            rules.append(
                "daylight and solar control should influence design"
            )



        # ==================================
        # OUTDOOR RELATIONSHIP
        # ==================================

        if (
            "garden" in requirements
            or
            "pool" in requirements
        ):


            constraints.append(
                "outdoor spaces should have meaningful architectural relationship"
            )


            rules.append(
                "living spaces should connect with outdoor areas"
            )



        # ==================================
        # DESIGN FREEDOM
        # ==================================

        freedoms.extend(

            [

                "building mass can adapt to site",

                "floor organization can vary",

                "open space strategy can vary",

                "architectural form can evolve based on concept"

            ]

        )



        return {


            "constraints":
            constraints,


            "design_freedom":
            freedoms,


            "architectural_rules":
            rules,


            "selected_strategy":
            selected_alternative,


            "source":
            "architectural_reasoning"

        }