# ==========================================================
# ArchitectOS Unified Runtime v37
# Runtime + Intent + Tool + Memory Context Fusion
# ==========================================================


from core.intent_router_v71 import intent_router

from core.tool_bootstrap import build_tool_registry

from core.memory.memory_manager import memory_manager

from core.memory.context_builder import context_builder

from core.prompt_engine import PromptEngine

from core.llm.llm_gateway_v30 import llm_gateway



class ArchitectOSRuntimeV37:


    VERSION = "37.0"



    def __init__(self):


        self.memory = memory_manager

        self.context = context_builder

        self.prompt_engine = PromptEngine()

        self.llm = llm_gateway


        self.tools = build_tool_registry(

            brain=self,

            memory=self.memory

        )


        print(
            "🚀 ARCHITECTOS RUNTIME v37 ONLINE"
        )



    # ======================================================
    # LLM BRIDGE
    # ======================================================


    def generate(
        self,
        message
    ):


        context = self.context.build(
            message
        )


        prompt = self.prompt_engine.build(

            message,

            context

        )


        result = self.llm.generate(

            prompt

        )


        return result.get(
            "response",
            ""
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


        self.memory.save_conversation(

            message,

            "user"

        )



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

                "error":
                "tool_not_found"

            }



        result = tool.execute(

            message,

            context=self.context.build(

                message,

                intent

            )

        )



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


architectos_runtime = ArchitectOSRuntimeV37()