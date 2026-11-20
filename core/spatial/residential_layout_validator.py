"""
ArchitectOS Residential Layout Validator v1.0

Checks residential spatial quality.
"""


class ResidentialLayoutValidator:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🏘 Residential Layout Validator v{self.VERSION} ACTIVE"
        )



    # ==================================================
    # LIGHT CHECK
    # ==================================================

    def check_room_light(
        self,
        rooms
    ):


        result = True


        for room in rooms:


            if room["type"] in [

                "bedroom",

                "living"

            ]:


                if "light_source" not in room:

                    result = False



        return result



    # ==================================================
    # VENTILATION CHECK
    # ==================================================

    def check_ventilation(
        self,
        rooms
    ):


        result = True


        for room in rooms:


            if room["type"] in [

                "bathroom",

                "kitchen"

            ]:


                if "ventilation" not in room:

                    result = False



        return result



    # ==================================================
    # LIGHTWELL CHECK
    # ==================================================

    def check_lightwell(
        self,
        lightwell,
        min_width=3,
        min_area=12
    ):


        return (

            lightwell.get(
                "width",
                0
            )

            >=

            min_width

            and

            lightwell.get(
                "area",
                0
            )

            >=

            min_area

        )



    # ==================================================
    # MAIN VALIDATE
    # ==================================================

    def validate(
        self,
        layout,
        lightwell=None
    ):


        checks = {


            "bedroom_light":
                True,


            "bathroom_ventilation":
                True,


            "kitchen_ventilation":
                True,


            "lightwell":
                True

        }



        for unit in layout.get(
            "units",
            []
        ):


            rooms = unit.get(
                "rooms",
                []
            )


            if not self.check_room_light(
                rooms
            ):

                checks["bedroom_light"] = False



            if not self.check_ventilation(
                rooms
            ):

                checks["bathroom_ventilation"] = False

                checks["kitchen_ventilation"] = False



        if lightwell:


            checks["lightwell"] = self.check_lightwell(

                lightwell

            )



        return {


            "valid":

                all(
                    checks.values()
                ),


            "checks":

                checks,


            "warnings":

                []

        }