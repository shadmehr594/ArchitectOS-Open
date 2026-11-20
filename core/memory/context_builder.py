# ==========================================================
# ArchitectOS Context Builder v29
# Unified Runtime Context
# Conversation + Profile + Personal + Intelligence Memory
# ==========================================================


from .memory_manager import memory_manager
from .memory_fusion import MemoryFusion
from .personal_context_engine import personal_context_engine
from .memory_intelligence_v31 import memory_intelligence
from core.memory.render_experience import RenderExperienceMemory
from core.prompt_intelligence.architectural_intent import ArchitecturalIntent



class ContextBuilder:


    VERSION = "v29"



    def __init__(self):


        self.memory = memory_manager

        self.fusion = MemoryFusion()

        self.personal = personal_context_engine

        self.intelligence = memory_intelligence

        self.architectural_intent_engine = (
            ArchitecturalIntent()
        )

        self.render_experience = (
            RenderExperienceMemory()
        )


        print(
            "🧠 CONTEXT BUILDER v29 ONLINE"
        )



    # ======================================================
    # BUILD
    # ======================================================

    def build(
        self,
        query,
        task=None,
        session_id=None
    ):


        if task is None:


            text = query.lower()


            design_keywords = [

                # Persian
                "طراحی",
                "طراح",
                "بساز",
                "ساخت",
                "خانه",
                "ویلا",
                "ساختمان",
                "معماری",
                "پلان",
                "اتاق",
                "فضا",

                # English
                "design",
                "designer",
                "build",
                "building",
                "house",
                "villa",
                "architecture",
                "architectural",
                "plan",
                "room",
                "space"
            ]


            if any(
                keyword in text
                for keyword in design_keywords
            ):

                task = "architecture"


            else:

                task = "chat"



        context = {


            "input":

                query,


            "task":

                task,


            "memory":

                {},


            "personal_context":

                {},


            "smart_memory":

                {}

        }



        # ----------------------------------
        # MEMORY FUSION
        # ----------------------------------

        try:


            context["memory"] = (

                self.fusion.build(
                    query,
                    session_id=session_id
                )

            )


        except Exception:


            context["memory"] = {}



        # ----------------------------------
        # PERSONAL CONTEXT
        # ----------------------------------

        try:


            context["personal_context"] = (

                self.personal.build()

            )


        except Exception:


            context["personal_context"] = {}



        # ----------------------------------
        # MEMORY INTELLIGENCE v31
        # ----------------------------------

        try:


            context["smart_memory"] = (

                self.intelligence.build(
                    query
                )

            )


        except Exception:


            context["smart_memory"] = {}



        # ======================================================
        # RENDER EXPERIENCE MEMORY BRIDGE v1
        # ======================================================

        try:

            context["render_experience"] = (
                self.render_experience.get_context()
            )


        except Exception as e:

            print(
                "RENDER EXPERIENCE BRIDGE ERROR:",
                e
            )

            context["render_experience"] = {}



        # ======================================================
        # ARCHITECTURAL INTENT BRIDGE
        # ======================================================

        try:

            if task == "architecture":

                context["architectural_intent"] = (
                    self.architectural_intent_engine.extract(
                        {
                            "prompt": query
                        }
                    )
                )

                print(
                    "🚨 CONTEXT BUILDER ARCH INTENT:",
                    context["architectural_intent"]
                )

            else:

                context["architectural_intent"] = {}

        except Exception as e:

            print(
                "ARCH INTENT CONTEXT ERROR:",
                e
            )

            context["architectural_intent"] = {}



        return context





# ==========================================================
# SINGLETON
# ==========================================================


context_builder = ContextBuilder()