"""
ArchitectOS Moving Ramp 3D Geometry Engine v1.0

Converts moving ramp parameters into 3D BIM geometry.
"""


class MovingRamp3DGeometryEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🏗️ Moving Ramp 3D Geometry Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # GENERATE 3D GEOMETRY
    # ==================================================

    def generate(
        self,
        ramp
    ):


        height = ramp.get(
            "height",
            3.2
        )


        slope = ramp.get(
            "slope",
            10
        )


        width = ramp.get(
            "width",
            1.5
        )


        segments_count = ramp.get(
            "segments",
            10
        )


        start_z = ramp.get(
            "start_z",
            0
        )


        end_z = start_z + height



        segment_height = round(
            height / segments_count,
            3
        )



        segments = []



        for i in range(
            segments_count + 1
        ):


            segments.append(

                {

                    "segment":
                        i + 1,


                    "z":
                        round(
                            start_z +
                            (segment_height * i),
                            3
                        )

                }

            )



        return {


            "type":

                "IfcTransportElement",


            "system":

                "moving_ramp",


            "slope":

                slope,


            "width":

                width,


            "start_z":

                start_z,


            "end_z":

                end_z,


            "segments":

                segments,


            "handrail":

                True,


            "side_panels":

                True,


            "landing_start":

                True,


            "landing_end":

                True

        }