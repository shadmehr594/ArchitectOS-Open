# ==========================================================
# ArchitectOS Prompt Context Injector v1
# Personal Context -> LLM Prompt Bridge
# ==========================================================


from core.memory.personal_context_engine import PersonalContextEngine



class PromptContextInjector:


    VERSION = "v1"



    def __init__(self):

        self.context_engine = PersonalContextEngine()

        print(
            "🧠 PROMPT CONTEXT INJECTOR v1 ONLINE"
        )



    # ======================================================
    # BUILD LLM CONTEXT
    # ======================================================

    def build_context(
        self,
        query
    ):


        try:

            context = self.context_engine.build(
                query
            )


        except Exception as e:

            return {

                "query": query,

                "personal_context": {},

                "error": str(e)

            }



        return {

            "query": query,

            "personal_context": context

        }



    # ======================================================
    # FORMAT FOR PROMPT
    # ======================================================

    def format_context(
        self,
        query
    ):


        data = self.build_context(
            query
        )


        context = data.get(
            "personal_context",
            {}
        )


        return f"""

USER PERSONAL CONTEXT:

{context}

USER REQUEST:

{query}

"""





# ==========================================================
# SINGLETON
# ==========================================================


prompt_context_injector = PromptContextInjector()