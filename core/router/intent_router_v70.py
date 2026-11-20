# ==========================================================
# ArchitectOS Intent Router v70
# Unified Request Classification
# ==========================================================


class IntentRouterV70:


    VERSION = "70.0"


    def __init__(self):

        print(
            "🧠 INTENT ROUTER v70 ONLINE"
        )


    # ======================================================
    # CLASSIFY
    # ======================================================

    def classify(
        self,
        message
    ):

        text = message.lower()


        # ------------------------------
        # IMAGE
        # ------------------------------

        image_words = [

            "image",
            "تصویر",
            "عکس",
            "نقاشی",
            "draw",
            "generate image"

        ]


        for word in image_words:

            if word in text:

                return "image"



        # ------------------------------
        # DESIGN
        # ------------------------------

        design_words = [

            "طراحی",
            "معماری",
            "ویلا",
            "ساختمان",
            "plan",
            "design",
            "floor"

        ]


        for word in design_words:

            if word in text:

                return "design"



        # ------------------------------
        # MEMORY
        # ------------------------------

        memory_words = [

            "یادت",
            "remember",
            "memory"

        ]


        for word in memory_words:

            if word in text:

                return "memory"



        # ------------------------------
        # DEFAULT
        # ------------------------------

        return "chat"




# singleton

intent_router = IntentRouterV70()