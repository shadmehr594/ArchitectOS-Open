"""
ArchitectOS Moving Ramp Spatial Placement Engine v1.0

Places moving ramps inside architectural spaces.
"""


class MovingRampSpatialPlacementEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"📐 Moving Ramp Spatial Placement Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # PLACE MOVING RAMP
    # ==================================================

    def place(
        self,
        ramp,
        origin=(0,0),
        orientation="horizontal",
        location="mall_atrium",
        shape="straight"
    ):


        x, y = origin


        length = ramp.get(
            "length",
            20
        )


        width = ramp.get(
            "width",
            1.5
        )



        if shape == "L":


            polygon = [

                [x,y],

                [x+length/2,y],

                [x+length/2,y+length/2],

                [x,y+length/2]

            ]



            exit_point = [

                x,

                y+length/2

            ]



        else:


            if orientation == "vertical":


                polygon = [

                    [x,y],

                    [x,y+length],

                    [x+width,y+length],

                    [x+width,y]

                ]


                exit_point=[

                    x,

                    y+length

                ]


            else:


                polygon = [

                    [x,y],

                    [x+length,y],

                    [x+length,y+width],

                    [x,y+width]

                ]


                exit_point=[

                    x+length,

                    y

                ]



        return {


            "type":

                "IfcTransportElement",


            "system":

                "moving_ramp",


            "shape":

                shape,


            "location":

                location,


            "polygon":

                polygon,


            "entry_point":

                [x,y],


            "exit_point":

                exit_point,


            "handrail":

                True,


            "landing":

                True

        }