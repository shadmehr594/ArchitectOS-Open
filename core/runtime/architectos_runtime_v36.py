# ==========================================================
# ArchitectOS Unified Runtime v36
# Runtime + Intent + Tool + Memory Bridge
# ==========================================================


from core.intent_router_v70 import intent_router

from core.tool_bootstrap import build_tool_registry

from core.memory.memory_manager import memory_manager

from core.llm.llm_gateway_v30 import llm_gateway



class ArchitectOSRuntimeV36:


    VERSION = "36.0"



    def __init__(self):


        self.memory = memory_manager


        self.tools = build_tool_registry(


            memory=self.memory,


            brain=llm_gateway


        )


        print(
            "🚀 ARCHITECTOS RUNTIME v36 ONLINE"
        )



    # ======================================================
    # RUN
    # ======================================================


    def run(
        self,
        message
    ):


        intent = intent_router.classify(
            message
        )


        print(
            "🧠 RUNTIME INTENT:",
            intent
        )


        # ------------------------------
        # SAVE USER MEMORY
        # ------------------------------

        self.memory.save_conversation(
            message,
            "user"
        )



        # ------------------------------
        # SELECT TOOL
        # ------------------------------


        if intent == "design":

            tool_name = "design"


        elif intent == "image":

            tool_name = "image"


        else:

            tool_name = "chat"



        tool = self.tools.get(
            tool_name
        )


        if not tool:

            return {

                "runtime":
                    self.VERSION,

                "error":
                    "tool_not_found"

            }



        result = tool.execute(

            message,

            context={

                "memory":
                    self.memory.get_history()

            }

        )



        # ------------------------------
        # SAVE RESPONSE
        # ------------------------------


        if isinstance(result, dict):

            output = result.get(
                "output",
                str(result)
            )

        else:

            output = str(result)



        self.memory.save_conversation(

            output,

            "assistant"

        )



        return {


            "runtime":
                self.VERSION,


            "intent":
                intent,


            "tool":
                tool_name,


            "result":
                result,


            "memory":

                {

                    "history":
                        len(
                            self.memory.get_history()
                        )

                }

        }





# ==========================================================
# SINGLETON
# ==========================================================


architectos_runtime = ArchitectOSRuntimeV36()