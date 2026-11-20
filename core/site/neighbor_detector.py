"""
ArchitectOS Neighbor Detector v1.0

Analyzes site neighbors and boundary relationships.

Features:
- Neighbor side detection
- Shared wall detection
- Light permission
- Open side detection
"""


class NeighborDetector:

    VERSION = "1.0"


    def __init__(self):

        print(
            f"🏘 Neighbor Detector v{self.VERSION} ACTIVE"
        )


    # ==========================================
    # DEFAULT SIDES
    # ==========================================

    SIDES = [
        "north",
        "south",
        "east",
        "west"
    ]


    # ==========================================
    # MAIN ANALYSIS
    # ==========================================

    def analyze(
        self,
        site
    ):

        neighbors = site.get(
            "neighbors",
            []
        )

        roads = site.get(
            "roads",
            []
        )


        result = {}


        for side in self.SIDES:

            result[side] = {

                "exists":
                    False,

                "neighbor_type":
                    None,

                "shared_wall":
                    False,

                "light_allowed":
                    True,

                "road":
                    False,

                "access":
                    False

            }



        # ======================================
        # NEIGHBORS
        # ======================================

        for neighbor in neighbors:

            side = neighbor.get(
                "side"
            )


            if side in result:

                result[side]["exists"] = True

                result[side]["neighbor_type"] = (
                    neighbor.get(
                        "type",
                        "unknown"
                    )
                )


                if neighbor.get(
                    "type"
                ) == "building":

                    result[side]["shared_wall"] = True

                    result[side]["light_allowed"] = False



        # ======================================
        # ROADS
        # ======================================

        for road in roads:

            side = road.get(
                "side"
            )


            if side in result:

                result[side]["road"] = True

                result[side]["access"] = True

                result[side]["light_allowed"] = True



        # ======================================
        # DEBUG
        # ======================================

        print(
            "\n====== NEIGHBOR ANALYSIS ======"
        )


        for side, data in result.items():

            print(
                side,
                ":",
                data
            )


        return result