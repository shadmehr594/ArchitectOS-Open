# ==========================================================
# ArchitectOS LLM Compatibility Adapter
# core.llm -> LLM interface
# ==========================================================


from .llm_gateway import LLMGateway



class LLM:


    def __init__(self):

        self.gateway = LLMGateway()


        print(
            "🧠 LLM COMPATIBILITY ADAPTER ONLINE"
        )



    # ======================================================
    # ASK
    # Legacy interface for CognitiveAgent
    # ======================================================

    def ask(
        self,
        prompt
    ):


        result = self.gateway.generate(

            prompt

        )


        if result is None:

            return (
                "LLM unavailable."
            )


        return result



    # ======================================================
    # GENERATE
    # Direct interface
    # ======================================================

    def generate(
        self,
        prompt
    ):


        return self.gateway.generate(

            prompt

        )