"""
ArchitectOS Ramp Spatial Placement Engine v1.0

Converts ramp decisions into spatial geometry.
"""
from math import hypot


class RampSpatialPlacementEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"📐 Ramp Spatial Placement Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # STRAIGHT RAMP
    # ==================================================

    def create_straight_ramp(
        self,
        data
    ):


        length = data.get(
            "length",
            10
        )


        width = data.get(
            "width",
            6
        )


        if data.get("authoritative_placement"):
            entry = data.get("entry_point")
            direction = data.get("entry_direction")
            if not (
                isinstance(entry, (list, tuple)) and len(entry) >= 2
                and isinstance(direction, (list, tuple)) and len(direction) >= 2
            ):
                return {
                    "type": data.get("type"),
                    "shape": "straight",
                    "geometry_status": "authoritative_placement_unresolved",
                    "polygon": [],
                    "centerline": [],
                    "entry_point": None,
                    "exit_point": None,
                }
            magnitude = hypot(float(direction[0]), float(direction[1]))
            if magnitude <= 0:
                return {
                    "type": data.get("type"), "shape": "straight",
                    "geometry_status": "authoritative_direction_unresolved",
                    "polygon": [], "centerline": [], "entry_point": None, "exit_point": None,
                }
            ux, uy = float(direction[0]) / magnitude, float(direction[1]) / magnitude
            nx, ny = -uy * width / 2.0, ux * width / 2.0
            entry = [float(entry[0]), float(entry[1])]
            exit_point = [entry[0] + ux * length, entry[1] + uy * length]
            return {
                "type": data.get("type"), "shape": "straight",
                "polygon": [[entry[0]+nx, entry[1]+ny], [exit_point[0]+nx, exit_point[1]+ny],
                            [exit_point[0]-nx, exit_point[1]-ny], [entry[0]-nx, entry[1]-ny]],
                "centerline": [entry, exit_point],
                "entry_point": entry, "exit_point": exit_point,
                "entry_direction": [ux, uy], "geometry_status": "resolved_from_authoritative_entry",
            }

        return {


            "type":
                data.get(
                    "type"
                ),


            "shape":
                "straight",


            "polygon":

            [

                [0,0],

                [length,0],

                [length,width],

                [0,width]

            ],


            "entry_point":
                [0,0],


            "exit_point":
                [length,0]

            ,"centerline":
                [[0,0], [length,0]]

        }



    # ==================================================
    # L RAMP
    # ==================================================

    def create_l_ramp(
        self,
        data
    ):


        length = data.get(
            "length",
            20
        )


        width = data.get(
            "width",
            6
        )


        segment = length / 2



        return {


            "type":
                data.get(
                    "type"
                ),


            "shape":
                "L",


            "polygon":

            [

                [0,0],

                [segment,0],

                [segment,width],

                [segment,width+segment],

                [0,width+segment],

                [0,width]

            ],


            "entry_point":
                [0,0],


            "exit_point":
                [segment,width+segment]

        }



    # ==================================================
    # U RAMP
    # ==================================================

    def create_u_ramp(
        self,
        data
    ):


        length = data.get(
            "length",
            30
        )


        width = data.get(
            "width",
            6
        )


        return {


            "type":
                data.get(
                    "type"
                ),


            "shape":
                "U",


            "polygon":

            [

                [0,0],

                [length,0],

                [length,width],

                [width,width],

                [width,length],

                [0,length]

            ],


            "entry_point":
                [0,0],


            "exit_point":
                [0,length]

        }



    # ==================================================
    # MAIN
    # ==================================================

    def generate(
        self,
        ramp_decision
    ):


        shape = ramp_decision.get(
            "shape",
            "straight"
        )



        if shape == "straight":

            return self.create_straight_ramp(
                ramp_decision
            )



        if shape == "L":

            return self.create_l_ramp(
                ramp_decision
            )



        if shape == "U":

            return self.create_u_ramp(
                ramp_decision
            )



        return self.create_straight_ramp(
            ramp_decision
        )
