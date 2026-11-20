# ==========================================================
# ArchitectOS Confirmation Handler v69
# Persistent Confirmation State
# ==========================================================


class ConfirmationHandler:


    def __init__(self):

        print(
            "✅ Confirmation Handler v69 ACTIVE"
        )


        self.state = {

            "pending_plan": None,

            "pending_message": None

        }



    # ======================================================
    # STORE EXECUTION REQUEST
    # ======================================================

    def store(
        self,
        plan,
        message
    ):


        self.state["pending_plan"] = plan

        self.state["pending_message"] = message



        print(
            "⏳ PLAN STORED FOR CONFIRMATION"
        )



        return {


            "status":

                "waiting_confirmation",


            "message":

                "Waiting for user approval",


            "plan":

                self._serialize_plan(plan)

        }




    # ======================================================
    # CONFIRM
    # ======================================================

    def confirm(
        self,
        message
    ):


        text = message.lower()



        approved_words = [

            "yes",
            "ok",
            "approve",
            "approved",
            "confirm",
            "اجرا",
            "تایید",
            "بله"

        ]



        if not any(
            word in text
            for word in approved_words
        ):


            return {

                "status":

                    "rejected",


                "message":

                    "Execution cancelled"

            }




        plan = self.state.get(
            "pending_plan"
        )



        prompt = self.state.get(
            "pending_message"
        )



        if plan is None:


            return {


                "status":

                    "error",


                "message":

                    "No pending execution plan"

            }




        # clear after approval

        self.state["pending_plan"] = None

        self.state["pending_message"] = None



        return {


            "status":

                "approved",


            "plan":

                plan,


            "prompt":

                prompt

        }




    # ======================================================
    # SERIALIZER
    # ======================================================

    def _serialize_plan(
        self,
        plan
    ):


        if hasattr(plan, "__dict__"):

            return plan.__dict__



        return plan





confirmation_handler = ConfirmationHandler()