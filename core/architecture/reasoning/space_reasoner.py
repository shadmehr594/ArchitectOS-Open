from core.architecture.model.space_model import SpaceModel



class SpaceReasoner:


    def analyze(
        self,
        spaces
    ):

        result = []


        for space in spaces:


            model = SpaceModel(
                space
            )


            if space == "living_room":

                model.category = "semi_public"

                model.add_property(
                    "role",
                    "social gathering"
                )

                model.add_property(
                    "needs",
                    [
                        "natural_light",
                        "outdoor_relation",
                        "visual_quality"
                    ]
                )

                model.add_relationship(
                    "terrace",
                    "direct_connection"
                )



            elif space == "bedroom":


                model.category = "private"

                model.add_property(
                    "role",
                    "rest_and_privacy"
                )

                model.add_property(
                    "needs",
                    [
                        "privacy",
                        "daylight"
                    ]
                )


            result.append(
                model
            )


        return result