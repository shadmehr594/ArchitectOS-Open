# ==========================================================
# ArchitectOS Runtime v35
# Unified Tool Orchestration Runtime
# ==========================================================


from core.intent_router_v70 import intent_router
from core.tool_bootstrap import build_tool_registry



class ArchitectOSRuntimeV35:


    VERSION = "35.0"



    def __init__(self):


        self.registry = build_tool_registry()


        print(
            "🚀 ARCHITECTOS RUNTIME v35 ONLINE"
        )



    # ======================================================
    # INTENT ROUTING
    # ======================================================


    def resolve_tool(
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



        if intent == "design":

            return (
                "design",
                intent
            )


        if intent == "image":

            return (
                "image",
                intent
            )


        return (
            "chat",
            intent
        )



    # ======================================================
    # EXECUTE
    # ======================================================


    def run(
        self,
        message,
        context=None
    ):


        tool_name, intent = self.resolve_tool(

            message

        )


        tool = self.registry.get(

            tool_name

        )



        if not tool:


            return {

                "status":
                    "error",

                "message":
                    f"tool {tool_name} not found"

            }



        result = tool.execute(

            message,

            context

        )



        return {


            "runtime":

                self.VERSION,


            "intent":

                intent,


            "tool":

                tool_name,


            "result":

                result

        }





# ==========================================================
# SINGLETON
# ==========================================================


architectos_runtime = ArchitectOSRuntimeV35()