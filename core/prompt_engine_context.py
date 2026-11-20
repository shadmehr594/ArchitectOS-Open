# ==========================================================
# ArchitectOS Prompt Engine Context Fusion v3.1
# Personal Memory Aware Prompt Layer
# ==========================================================


from core.prompt_engine import PromptEngine
from core.ai.prompt_context_injector import (
    prompt_context_injector
)



class PromptContextEngine:


    VERSION = "3.1"



    def __init__(self):

        self.base_engine = PromptEngine()

        self.context_injector = prompt_context_injector


        print(
            "🧠 PROMPT ENGINE CONTEXT FUSION v3.1 ONLINE"
        )



    # ======================================================
    # BUILD CONTEXT AWARE PROMPT
    # ======================================================

    def build(
        self,
        user
    ):


        personal_context = (
            self.context_injector.build_context(
                user
            )
        )


        prompt = self.base_engine.build(
            user,
            personal_context
        )


        return prompt



# ==========================================================
# SINGLETON
# ==========================================================


prompt_context_engine = PromptContextEngine()