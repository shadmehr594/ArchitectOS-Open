# ==========================================================
# SPATIAL DECISION ENGINE V1
# SPATIAL INTENT TO DESIGN DECISION LAYER
# ==========================================================


class SpatialDecisionEngineV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧠 Spatial Decision Engine v1.0 ACTIVE"
        )



    # ======================================================
    # GENERATE SPATIAL DECISIONS
    # ======================================================


    def decide(
        self,
        spatial_intent
    ):


        decisions = {}



        if not isinstance(
            spatial_intent,
            dict
        ):

            return {

                "engine":
                    "SPATIAL_DECISION_ENGINE_V1",

                "version":
                    self.VERSION,

                "decisions":
                    decisions,

                "ready":
                    False

            }



        spaces = spatial_intent.get(
            "spaces",
            {}
        )



        if not isinstance(
            spaces,
            dict
        ):

            spaces = {}



        for space, data in spaces.items():


            if not isinstance(
                data,
                dict
            ):

                continue



            role = data.get(
                "role"
            )


            privacy = data.get(
                "privacy"
            )


            decision = {

                "preferred_zone":
                    "middle",

                "daylight":
                    "medium",

                "privacy_buffer":
                    False

            }



            # PUBLIC

            if role == "public_space":

                decision["preferred_zone"] = (
                    "front"
                )

                decision["daylight"] = (
                    "high"
                )



            # PRIVATE

            elif role == "private_space":

                decision["preferred_zone"] = (
                    "rear"
                )

                decision["privacy_buffer"] = (
                    True
                )



            # EXTERNAL

            elif role == "external_space":

                decision["preferred_zone"] = (
                    "external"
                )



            # SERVICE

            elif role == "service_space":

                decision["preferred_zone"] = (
                    "service"
                )



            if privacy == "high":

                decision["privacy_buffer"] = (
                    True
                )



            decisions[space] = decision



        return {


            "engine":

                "SPATIAL_DECISION_ENGINE_V1",


            "version":

                self.VERSION,


            "decisions":

                decisions,


            "ready":

                True

        }