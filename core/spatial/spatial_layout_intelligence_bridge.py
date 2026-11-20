"""
ArchitectOS Spatial Layout Intelligence Bridge v1.0

Converts architectural layout decisions
into spatial engine constraints.

Input:
    Architectural Layout Adapter output

Output:
    Spatial Layout Constraints
"""


class SpatialLayoutIntelligenceBridge:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"🧠 Spatial Layout Intelligence Bridge v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # CREATE CONSTRAINT
    # ==================================================

    def create_constraint(
        self,
        constraint_type,
        space,
        target=None
    ):


        return {

            "type":
                constraint_type,


            "space":
                space,


            "target":
                target

        }



    # ==================================================
    # CONVERT LAYOUT DECISION
    # ==================================================

    def generate_constraints(
        self,
        layout_decision
    ):


        constraints = []


        spaces = layout_decision.get(
            "spaces",
            []
        )


        for space in spaces:


            role = space.get(
                "layout_role"
            )


            space_id = space.get(
                "id"
            )



            # ------------------------------
            # CENTRAL SPACE
            # ------------------------------

            if role == "central_open_space":


                constraints.append(

                    self.create_constraint(

                        "center",

                        space_id

                    )

                )



            # ------------------------------
            # ADJACENT SPACE
            # ------------------------------

            elif role == "courtyard_adjacent":


                constraints.append(

                    self.create_constraint(

                        "adjacent",

                        space_id,

                        "courtyard_001"

                    )

                )



            else:


                constraints.append(

                    self.create_constraint(

                        "free",

                        space_id

                    )

                )



        return {


            "strategy":

                layout_decision.get(
                    "strategy"
                ),


            "constraints":

                constraints

        }