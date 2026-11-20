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


    def classify(
        self,
        message
    ):

        text = message.lower()


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



        memory_words = [
            "یادت",
            "remember",
            "memory"
        ]


        for word in memory_words:
            if word in text:
                return "memory"



        return "chat"



intent_router = IntentRouterV70()