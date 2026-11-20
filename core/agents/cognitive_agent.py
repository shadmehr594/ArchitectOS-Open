# ==========================================================
# ArchitectOS Cognitive Agent v74.3
# Chat -> TaskManager -> Cognition -> Runtime
# Intent Based Cognitive Routing Layer
# ==========================================================


from core.managers.cognition_manager import cognition_manager
from core.managers.task_manager import task_manager
from core.managers.runtime_manager import runtime_manager

from core.llm import LLM



class CognitiveAgent:


    def __init__(self):

        print(
            "🧠 Cognitive Agent v74.3 ACTIVE"
        )

        self.llm = LLM()



    # ======================================================
    # PROCESS MESSAGE
    # ======================================================

    def process(
        self,
        message
    ):


        print(
            "👤 COGNITIVE USER:",
            message
        )



        # ==================================================
        # MEMORY CONTEXT
        # ==================================================

        task_context = task_manager.process_message(
            message
        )


        user_context = task_context.get(
            "memory",
            {}
        )


        conversation_context = task_context.get(
            "context",
            {}
        )



        # ==================================================
        # COGNITION
        # ==================================================

        cognition = cognition_manager.analyze(
            message
        )


        intent = cognition.get(
            "intent"
        )


        plan = cognition.get(
            "plan"
        )



        intent_name = getattr(

            intent,

            "intent",

            "unknown"

        )



        workflow = getattr(

            plan,

            "workflow",

            "none"

        )



        engine = getattr(

            plan,

            "engine",

            "none"

        )



        print(
            "🧠 INTENT:",
            intent_name
        )



        # ==================================================
        # CHAT ROUTE
        # ==================================================

        if (

            intent_name == "chat"

            or

            self.is_chat_message(
                message
            )

        ):


            response = self.llm.ask(

                f"""

You are ArchitectOS AI assistant.

Conversation:

{conversation_context}


User:

{message}


Reply naturally in user's language.

"""

            )



            task_manager.save_response(

                message,

                response

            )


            return {


                "type":

                    "chat",


                "status":

                    "success",


                "intent":

                    {

                        "intent":

                            "chat"

                    },


                "message":

                    response

            }





        # ==================================================
        # DESIGN ROUTE
        # ONLY DESIGN REQUESTS ENTER GOD CORE
        # ==================================================

        if intent_name in [

            "design_request",
            "generic_building",
            "villa_design",
            "apartment_design",
            "highrise_design"

        ]:


            result = runtime_manager.execute(

                plan,

                message

            )


            return {


                "type":

                    "design",


                "status":

                    "success",


                "engine":

                    "GOD_CORE",


                "result":

                    result

            }





        # ==================================================
        # IMAGE / MEDIA ROUTE
        # ==================================================

        if intent_name in [

            "image_generation",

            "image_edit",

            "video_generation",

            "facade_edit",

            "material_change",

            "lighting_change"

        ]:


            result = runtime_manager.execute(

                plan,

                message

            )


            return {


                "type":

                    intent_name,


                "status":

                    "success",


                "workflow":

                    workflow,


                "engine":

                    engine,


                "result":

                    result

            }





        # ==================================================
        # FALLBACK
        # ==================================================

        response = self.llm.ask(

            message

        )


        return {


            "type":

                "chat",


            "status":

                "success",


            "intent":

                {

                    "intent":

                        intent_name

                },


            "message":

                response

        }





    # ======================================================
    # CHAT DETECTOR
    # ======================================================

    def is_chat_message(
        self,
        text
    ):


        words = [

            "سلام",
            "درود",
            "hello",
            "hi",
            "خوبی",
            "چطوری",
            "اسمت",
            "نامت",
            "کی هستی",
            "what is your name",
            "how are you"

        ]


        text = text.lower()


        return any(

            word in text

            for word in words

        )





    # ======================================================
    # CONFIRM
    # ======================================================

    def confirm(
        self,
        message
    ):


        return runtime_manager.confirm(
            message
        )





# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


cognitive_agent = CognitiveAgent()