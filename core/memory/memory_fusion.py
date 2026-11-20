# ==========================================================
# ArchitectOS Memory Fusion Engine v30
# Experience + Execution + Conversation
# User Profile + Personal Context
# ==========================================================


from .memory_manager import memory_manager
from .conversation_intelligence import ConversationIntelligence
from .user_profile_memory import user_profile_memory



class MemoryFusion:


    VERSION = "v30"



    def __init__(
        self
    ):


        self.memory = memory_manager

        self.conversation = ConversationIntelligence()

        self.user_profile = user_profile_memory


        print(
            "🧠 MEMORY FUSION ENGINE v30 ONLINE"
        )



    # ======================================================
    # BUILD INTELLIGENT MEMORY
    # ======================================================

    def build(
        self,
        query,
        session_id=None
    ):


        result = {


            "query":

                query,


            "experience":

                [],


            "executions":

                [],


            "conversation":

                {},


            "user_profile":

                {},


            "personal_context":

                {},


            "summary":

                {}

        }



        # ==================================================
        # EXPERIENCE
        # ==================================================

        try:

            result["experience"] = (

                self.memory.best_experiences()

                or []

            )


        except Exception:

            pass



        # ==================================================
        # EXECUTION
        # ==================================================

        try:


            execution_memory = getattr(

                self.memory,

                "execution",

                None

            )


            if execution_memory:


                result["executions"] = (

                    execution_memory.recent()

                )


        except Exception:

            pass



        # ==================================================
        # CONVERSATION
        # ==================================================

        try:


            history = self.memory.get_history(
                20,
                session_id=session_id
            )


            result["conversation"] = (

                self.conversation.analyze(
                    history
                )

            )


        except Exception:

            pass



        # ==================================================
        # USER PROFILE
        # ==================================================

        try:


            result["user_profile"] = (

                self.user_profile.get_profile()

            )


        except Exception:

            pass



        # ==================================================
        # PERSONAL CONTEXT BUILDER
        # ==================================================

        try:


            profile = result["user_profile"]


            result["personal_context"] = {


                "architecture_style":

                    profile.get(
                        "preferences",
                        {}
                    ).get(
                        "architecture_style"
                    ),


                "interests":

                    profile.get(
                        "interests",
                        []
                    ),


                "projects":

                    profile.get(
                        "projects",
                        {}
                    ),


                "family":

                    profile.get(
                        "family",
                        {}

                    ),


                "food_preferences":

                    profile.get(
                        "food_preferences",
                        {}

                    )

            }



        except Exception:

            result["personal_context"] = {}



        # ==================================================
        # SUMMARY
        # ==================================================

        result["summary"] = {


            "experience_count":

                len(
                    result["experience"]
                ),


            "execution_count":

                len(
                    result["executions"]
                ),


            "conversation_users":

                len(
                    result["conversation"].get(
                        "user_messages",
                        []
                    )
                ),


            "conversation_assistant":

                len(
                    result["conversation"].get(
                        "assistant_messages",
                        []
                    )
                ),


            "user_profile_sections":

                len(
                    result["user_profile"]
                ),


            "personal_context_sections":

                len(
                    result["personal_context"]
                )

        }


        return result