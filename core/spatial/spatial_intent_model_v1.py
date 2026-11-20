# ==========================================================
# SPATIAL INTENT MODEL V1
# SPACE PROGRAM -> SPATIAL DESIGN INTENT
# ==========================================================


class SpatialIntentModelV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧭 Spatial Intent Model v1.0 ACTIVE"
        )



    # ======================================================
    # BUILD SPATIAL INTENT
    # ======================================================


    def build(
        self,
        space_program
    ):


        spaces = (
            space_program.get(
                "spaces",
                []
            )
        )


        relationships = (
            space_program.get(
                "relationships",
                []
            )
        )


        zones = (
            space_program.get(
                "zones",
                {}
            )
        )



        intent = {}



        for space in spaces:


            intent[space] = {


                "role":

                    self.detect_role(
                        space,
                        zones
                    ),


                "connects":

                    [],


                "adjacent":

                    [],


                "privacy":

                    self.detect_privacy(
                        space,
                        zones
                    )

            }



        for relation in relationships:


            start = relation.get(
                "from"
            )


            end = relation.get(
                "to"
            )


            relation_type = relation.get(
                "type"
            )



            if start in intent:


                if relation_type == "adjacent":

                    intent[start]["adjacent"].append(
                        end
                    )


                else:

                    intent[start]["connects"].append(
                        end
                    )



        return {


            "engine":

                "SPATIAL_INTENT_MODEL_V1",


            "version":

                self.VERSION,


            "spaces":

                intent,


            "ready":

                True

        }



    # ======================================================
    # ROLE DETECTION
    # ======================================================


    def detect_role(
        self,
        space,
        zones
    ):


        for zone, items in zones.items():

            if space in items:


                if zone == "public":

                    return "public_space"


                if zone == "private":

                    return "private_space"


                if zone == "service":

                    return "service_space"


                if zone == "external":

                    return "external_space"



        return "general_space"



    # ======================================================
    # PRIVACY
    # ======================================================


    def detect_privacy(
        self,
        space,
        zones
    ):


        if space in zones.get(
            "private",
            []
        ):

            return "high"



        if space in zones.get(
            "service",
            []
        ):

            return "medium"



        if space in zones.get(
            "public",
            []
        ):

            return "low"



        return "medium"