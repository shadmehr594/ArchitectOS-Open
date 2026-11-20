"""
ArchitectOS Escalator 3D Geometry Engine v1.0

Creates 3D representation of escalators.
"""


import math



class Escalator3DGeometryEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🏗️ Escalator 3D Geometry Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # CREATE 3D GEOMETRY
    # ==================================================

    def generate(
        self,
        escalator,
        placement
    ):


        height = escalator.get(
            "height",
            3.0
        )


        angle = escalator.get(
            "angle",
            30
        )


        width = escalator.get(
            "width",
            1.0
        )


        steps = []


        riser_height = 0.18


        step_count = math.ceil(

            height /
            riser_height

        )



        actual_riser = round(

            height /
            step_count,

            3

        )



        for i in range(
            step_count + 1
        ):


            z = round(

                i *
                actual_riser,

                3

            )


            steps.append(

                {

                    "step":
                        i + 1,

                    "z":
                        z

                }

            )



        return {


            "type":

                "IfcTransportElement",



            "system":

                "escalator",



            "angle":

                angle,



            "width":

                width,



            "height":

                height,



            "steps":

                steps,



            "handrail":

                True,



            "side_panels":

                True,



            "placement":

                placement

        }