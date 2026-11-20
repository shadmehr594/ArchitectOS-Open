"""
ArchitectOS Escalator Spatial Placement Engine v1.0

Places escalator geometry inside architectural space.
"""


class EscalatorSpatialPlacementEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"📐 Escalator Spatial Placement Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # PLACE ESCALATOR
    # ==================================================

    def place(
        self,
        escalator,
        origin=(0,0),
        orientation="horizontal",
        location="atrium"
    ):


        x, y = origin


        length = escalator.get(
            "length",
            6.0
        )


        width = escalator.get(
            "width",
            1.0
        )



        if orientation == "vertical":


            polygon = [

                [x,y],

                [x,y+length],

                [x+width,y+length],

                [x+width,y]

            ]


        else:


            polygon = [

                [x,y],

                [x+length,y],

                [x+length,y+width],

                [x,y+width]

            ]



        return {


            "type":
                "IfcTransportElement",


            "system":
                "escalator",


            "location":
                location,


            "orientation":
                orientation,


            "polygon":
                polygon,


            "entry_point":

                [x,y],



            "exit_point":

                (
                    [x+length,y]
                    if orientation=="horizontal"
                    else
                    [x,y+length]
                ),



            "bottom_landing":
                True,


            "top_landing":
                True

        }