"""
ArchitectOS Intelligent Moving Ramp Design Engine v1.0

Designs moving ramps / travelators.
"""


import math



class MovingRampDesignEngine:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🛒 Moving Ramp Design Engine v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # DESIGN
    # ==================================================

    def design(
        self,
        height,
        width=1.5,
        slope=10,
        shopping_cart=True,
        wheelchair=True,
        landing=True,
        override=None
    ):


        if override is None:

            override = {}



        width = override.get(
            "width",
            width
        )


        slope = override.get(
            "slope",
            slope
        )


        shopping_cart = override.get(
            "shopping_cart",
            shopping_cart
        )


        wheelchair = override.get(
            "wheelchair",
            wheelchair
        )


        landing = override.get(
            "landing",
            landing
        )



        # slope percentage calculation

        length = round(

            height /
            (slope / 100),

            2

        )



        return {


            "type":
                "moving_ramp",


            "height":
                height,


            "slope":
                slope,


            "length":
                length,


            "width":
                width,


            "shopping_cart_allowed":
                shopping_cart,


            "wheelchair_allowed":
                wheelchair,


            "handrail":
                True,


            "landing":
                landing,


            "safety_zone":
                True

        }