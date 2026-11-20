"""
ArchitectOS Vertical Accessibility Intelligence v2.0

Reasoning agent for accessibility and ramp systems.
"""


class VerticalAccessibilityIntelligence:


    VERSION = "2.0"



    def __init__(self):

        print(
            f"♿ Vertical Accessibility Intelligence v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # ANALYZE ACCESSIBILITY NEED
    # ==================================================

    def analyze(
        self,
        context
    ):


        result = {

            "required": False,

            "systems": []

        }



        height = context.get(

            "height",

            0

        )


        user_type = context.get(

            "user_type",

            "pedestrian"

        )


        accessibility = context.get(

            "accessibility_required",

            True

        )


        space_limit = context.get(

            "limited_space",

            False

        )



        if not accessibility:

            return result



        if user_type == "vehicle":


            result["systems"].append(

                self.create_vehicle_ramp(

                    height,

                    space_limit

                )

            )


        else:


            result["systems"].append(

                self.create_accessible_ramp(

                    height,

                    space_limit

                )

            )


        result["required"] = True


        return result



    # ==================================================
    # RAMP LENGTH
    # ==================================================

    def calculate_ramp_length(
        self,
        height,
        slope
    ):


        if slope <= 0:

            return 0



        return round(

            height / (slope / 100),

            2

        )



    # ==================================================
    # HUMAN ACCESS RAMP
    # ==================================================

    def create_accessible_ramp(
        self,
        height,
        limited_space
    ):


        slope = 8


        if limited_space:

            slope = 10



        length = self.calculate_ramp_length(

            height,

            slope

        )



        return {


            "type":

                "accessible_ramp",


            "height":

                height,


            "slope":

                slope,


            "length":

                length,


            "landings":

                length > 6,


            "handrail":

                True

        }



    # ==================================================
    # VEHICLE RAMP
    # ==================================================

    def create_vehicle_ramp(
        self,
        height,
        limited_space
    ):


        slope = 15


        if limited_space:

            slope = 18



        length = self.calculate_ramp_length(

            height,

            slope

        )



        return {


            "type":

                "vehicle_ramp",


            "height":

                height,


            "slope":

                slope,


            "length":

                length,


            "turning_area":

                True

        }