"""
ArchitectOS Architectural Layout Adapter v1.0

Converts architectural space contracts
into spatial layout decisions.

Input:
    Architectural Space Contract

Output:
    Layout Strategy + Spatial Instructions
"""


class ArchitecturalLayoutAdapter:


    VERSION = "1.0"


    def __init__(self):

        print(
            f"🏛️ Architectural Layout Adapter v{self.VERSION} ACTIVE"
        )


    # ==================================================
    # DETECT LAYOUT STRATEGY
    # ==================================================

    def detect_strategy(
        self,
        spaces
    ):


        has_courtyard = any(

            space.get("type")
            ==
            "courtyard"

            for space in spaces

        )


        if has_courtyard:

            return (
                "courtyard_centered"
            )


        return (
            "standard_organization"
        )



    # ==================================================
    # BUILD LAYOUT DECISION
    # ==================================================

    def generate_layout(
        self,
        spaces
    ):


        strategy = self.detect_strategy(
            spaces
        )


        layout_spaces = []


        for space in spaces:


            node = {


                "id":

                    space.get(
                        "id"
                    ),


                "type":

                    space.get(
                        "type"
                    ),


                "layout_role":

                    None


            }


            # ------------------------------
            # COURTYARD
            # ------------------------------

            if space.get(
                "type"
            ) == "courtyard":


                node[
                    "layout_role"
                ] = "central_open_space"



            # ------------------------------
            # OTHER SPACES
            # ------------------------------

            else:


                adjacency = space.get(
                    "adjacency",
                    {}
                )


                if (
                    "courtyard"
                    in
                    adjacency.get(
                        "preferred",
                        []
                    )
                ):

                    node[
                        "layout_role"
                    ] = (
                        "courtyard_adjacent"
                    )


                else:


                    node[
                        "layout_role"
                    ] = (
                        "general_space"
                    )


            layout_spaces.append(
                node
            )



        return {


            "strategy":

                strategy,


            "spaces":

                layout_spaces


        }