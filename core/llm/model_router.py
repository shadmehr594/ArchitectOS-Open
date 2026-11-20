# ==========================================================
# ArchitectOS Model Router v1
# Safe Multi Model LLM Dispatcher
#
# CHAT_MODEL_ROUTING_V1 — the routes are no longer hardcoded to
# models that have been removed. They resolve from
# config/chat_config.py:
#
#   chat               -> ARCHITECTOS_CHAT_MODEL    (qwen3.8:27b)
#   reasoning / intent -> ARCHITECTOS_INTENT_MODEL  (defaults to chat)
#
# The router is a thin dispatcher only; it holds no model names.
# ==========================================================


from core.llm.llm_gateway_v30 import llm_gateway



class ModelRouter:


    VERSION = "1.0"



    def __init__(self):

        self.gateway = llm_gateway


        print(
            "🧠 MODEL ROUTER v1 ONLINE"
        )



    # ======================================================
    # CHAT
    # ======================================================


    def chat(
        self,
        prompt
    ):


        result = self.gateway.chat(

            prompt

        )


        return result.get(

            "response",

            ""

        )



    # ======================================================
    # REASONING
    # ======================================================


    def reason(
        self,
        prompt
    ):


        result = self.gateway.reason(

            prompt

        )


        return result.get(

            "response",

            ""

        )



    # ======================================================
    # AUTO SELECT
    # ======================================================


    def generate(
        self,
        prompt,
        task="chat"
    ):


        if task in [

            "reasoning",

            "intent",

            "architecture"

        ]:


            return self.reason(

                prompt

            )



        return self.chat(

            prompt

        )





# ==========================================================
# SINGLETON
# ==========================================================


model_router = ModelRouter()