# ==========================================================
# ArchitectOS Memory Manager v24.1
# Unified Memory Gateway
# Context + Conversation + Experience + Execution
# + User Profile Intelligence
# ==========================================================


from .user_memory import UserMemory
from .architect_memory import ArchitectMemory
from .store import MemoryStore
from .conversation_memory import ConversationMemory
from .execution_memory import ExecutionMemory

from .user_profile_memory import user_profile_memory
from .profile_extractor import ProfileExtractor



class MemoryManager:


    VERSION = "v24.1"



    def __init__(self):


        # ----------------------------------
        # CORE MEMORY
        # ----------------------------------

        self.user = UserMemory()

        self.experience = ArchitectMemory()

        self.store = MemoryStore()

        self.conversation = ConversationMemory()

        self.execution = ExecutionMemory()



        # ----------------------------------
        # USER PROFILE INTELLIGENCE
        # ----------------------------------

        self.profile = user_profile_memory


        self.profile_extractor = ProfileExtractor(
            self.profile
        )



        print(
            "🧠 MEMORY MANAGER v24.1 ONLINE"
        )



    # ======================================================
    # USER MEMORY
    # ======================================================

    def remember_user(
        self,
        facts
    ):

        return self.user.update(
            facts
        )



    def recall_user(
        self,
        key=None
    ):


        if key:

            return self.user.get(
                key
            )


        return self.user.all()



    # ======================================================
    # USER PROFILE
    # ======================================================

    def extract_profile(
        self,
        message
    ):

        return self.profile_extractor.extract(
            message
        )



    def get_profile(
        self
    ):

        return self.profile.get_profile()



    # ======================================================
    # CONTEXT MEMORY
    # ======================================================

    def save_context(
        self,
        item
    ):

        return self.store.write(
            item
        )



    def get_context(
        self
    ):

        return self.store.read()



    # ======================================================
    # GENERAL RECALL
    # ======================================================

    def recall(
        self,
        query=None
    ):


        context = self.get_context()


        if context:

            return context


        return self.search(
            query
        )



    # ======================================================
    # MEMORY SEARCH
    # ======================================================

    def search(
        self,
        query=None
    ):


        results = []


        if not query:

            return results



        query = str(
            query
        ).lower()



        for item in self.get_history(100):


            message = str(
                item.get(
                    "message",
                    ""
                )
            )


            if query in message.lower():

                results.append(
                    item
                )



        return results



    # ======================================================
    # CONVERSATION MEMORY
    # ======================================================

    def save_conversation(
        self,
        message,
        message_type="chat",
        session_id=None
    ):


        try:

            if message_type == "user":


                profile_data = self.profile_extractor.extract(
                    message
                )


                if profile_data:


                    print(
                        "🧠 PROFILE UPDATED:",
                        profile_data
                    )


        except Exception as e:


            print(
                "⚠️ PROFILE EXTRACTION ERROR:",
                e
            )



        return self.conversation.add(
            message,
            message_type,
            session_id=session_id
        )



    def get_history(
        self,
        limit=20,
        session_id=None
    ):

        return self.conversation.history(
            limit,
            session_id=session_id
        )


    def replace_conversation_session(
        self,
        session_id,
        entries
    ):
        """SENT_MESSAGE_EDIT_V1 — rebuild ONE session's in-process history.

        Delegates to the existing store; it owns the message list and the
        session tagging, so the replacement can never touch another
        project's entries.
        """

        return self.conversation.replace_session(
            session_id,
            entries
        )



    # ======================================================
    # EXPERIENCE MEMORY
    # ======================================================

    def save_experience(
        self,
        project,
        analysis
    ):

        return self.experience.store(
            project,
            analysis
        )



    def best_experiences(
        self
    ):

        return self.experience.retrieve_best()



    # ======================================================
    # EXECUTION MEMORY
    # ======================================================

    def save_execution(
        self,
        engine,
        result
    ):

        return self.execution.store(
            engine,
            result
        )



    def execution_history(
        self,
        limit=20
    ):

        return self.execution.history(
            limit
        )



    # ======================================================
    # FULL MEMORY RECALL
    # ======================================================

    def recall_everything(
        self,
        query=None
    ):


        return {


            "profile":

                self.get_profile(),



            "user_memory":

                self.recall_user(),



            "conversation":

                self.get_history(
                    50
                ),



            "experience":

                self.best_experiences(),



            "execution":

                self.execution_history(
                    20
                ),



            "context":

                self.get_context(),



            "query":

                query

        }





# ==========================================================
# SINGLETON
# ==========================================================


memory_manager = MemoryManager()