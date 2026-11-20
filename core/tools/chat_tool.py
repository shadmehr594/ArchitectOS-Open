# ==========================================================
# ArchitectOS Chat Tool v38.1
# Unified LLM Chat Interface
# Runtime owns Brain Pipeline
# ==========================================================


from core.tools.base import BaseTool



class ChatTool(BaseTool):


    name = "chat"


    VERSION = "38.1"



    def __init__(
        self,
        brain=None,
        memory=None
    ):

        self.brain = brain

        self.memory = memory


        print(
            "💬 CHAT TOOL v38.1 ONLINE"
        )



    # ======================================================
    # TASK GUARD
    # ======================================================


    def is_task_request(
        self,
        text
    ):


        text = (
            text or ""
        ).lower()



        keywords = [

            "design",
            "architecture",
            "draw",
            "plan",

            "طراحی",
            "معماری",
            "نقشه",
            "ساختمان",
            "ویلا"

        ]



        return any(

            k in text

            for k in keywords

        )



    # ======================================================
    # EXECUTE
    # ======================================================


    def execute(
        self,
        state,
        context=None
    ):


        try:


            state = (

                state or ""

            ).strip()



            # ==============================================
            # PROFILE RECALL
            # ==============================================


            if self.memory:


                text = state.lower()



                profile_questions = [

                    "اسم من چیه",
                    "نام من چیه",
                    "who am i"

                ]



                if any(

                    q in text

                    for q in profile_questions

                ):



                    profile = (

                        self.memory.get_profile()

                    )



                    name = (

                        profile

                        .get(
                            "user",
                            {}
                        )

                        .get(
                            "name"
                        )

                    )



                    if name:


                        return {


                            "output":

                                f"اسم شما {name} است.",



                            "type":

                                "chat"

                        }




            # ==============================================
            # BRAIN PIPELINE
            # Runtime owns:
            # Context Builder
            # Prompt Engine
            # LLM Gateway
            # ==============================================


            if self.brain and hasattr(

                self.brain,

                "generate"

            ):


                response = self.brain.generate(

                    state

                )



                # Normalize LLM output

                if isinstance(
                    response,
                    dict
                ):


                    response = response.get(

                        "response",

                        str(response)

                    )



                return {


                    "output":

                        response,



                    "type":

                        "chat"

                }




            # ==============================================
            # NO BRAIN
            # ==============================================


            return {


                "output":

                    "ArchitectOS Brain is unavailable.",



                "type":

                    "error"

            }




        except Exception as e:



            return {


                "output":

                    f"error: {str(e)}",



                "type":

                    "error"

            }