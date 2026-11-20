# ==========================================================
# ArchitectOS Reasoning Context Builder v1
# GOD CORE -> Architectural Reasoning Engine Adapter
# ==========================================================


class ReasoningContextBuilder:


    VERSION = "1.0"



    def __init__(self):

        print(
            f"🧠 Reasoning Context Builder v{self.VERSION} ACTIVE"
        )



    # ======================================================
    # BUILD CONTEXT
    # ======================================================

    def build(
        self,
        design,
        plan,
        user_input=""
    ):


        context = {


            "climate":

                "",


            "facade":

                {


                    "south":

                        {


                            "openings":

                                []

                        }


                },


            "roof":

                {


                    "green_roof":

                        False

                }


        }



        text = (

            user_input

            or

            ""

        ).lower()



        # ==================================================
        # CLIMATE INFERENCE
        # ==================================================

        if (

            "جنوب"

            in

            text

            or

            "hot"

            in

            text

            or

            "گرم"

            in

            text

        ):


            context["climate"] = "hot"



        # ==================================================
        # OPENING INFERENCE
        # ==================================================

        if (

            "پنجره"

            in

            text

            or

            "window"

            in

            text

        ):


            width = 3


            context["facade"]["south"]["openings"].append(

                {


                    "type":

                        "window",


                    "width":

                        width


                }

            )



        # ==================================================
        # ROOF DETECTION
        # ==================================================

        if (

            "بام سبز"

            in

            text

            or

            "green roof"

            in

            text

        ):


            context["roof"]["green_roof"] = True



        return context





# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


reasoning_context_builder = ReasoningContextBuilder()