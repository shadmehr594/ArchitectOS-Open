# ==========================================================
# ArchitectOS Personal Context Engine v1
# User-Aware Context Layer
# ==========================================================


from .user_profile_memory import user_profile_memory
from .memory_intelligence_engine import (
    memory_intelligence_engine
)



class PersonalContextEngine:


    VERSION = "v1"



    def __init__(self):

        self.profile = user_profile_memory

        self.memory = memory_intelligence_engine


        print(
            "🧠 PERSONAL CONTEXT ENGINE v1 ONLINE"
        )



    # ======================================================
    # BUILD PERSONAL CONTEXT
    # ======================================================

    def build(
        self,
        query=None
    ):


        profile = self.profile.get_profile()


        smart_memory = {}


        if query:


            smart_memory = self.memory.build(
                query
            )



        context = {


            "identity":

                profile.get(
                    "user",
                    {}
                ),



            "domains":

                profile.get(
                    "interests",
                    []
                ),



            "preferences":

                profile.get(
                    "preferences",
                    {}
                ),



            "family_context":

                profile.get(
                    "family",
                    {}
                ),



            "project_context":

                profile.get(
                    "projects",
                    {}
                ),



            "lifestyle":

                {


                    "food":

                    profile.get(
                        "food_preferences",
                        {}
                    )


                },



            "smart_memory":

                smart_memory.get(
                    "matched",
                    {}
                ),



            "confidence":

                smart_memory.get(
                    "confidence",
                    {})

        }


        return context





# ==========================================================
# SINGLETON
# ==========================================================


personal_context_engine = PersonalContextEngine()