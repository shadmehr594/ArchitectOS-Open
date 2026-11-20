# ==========================================================
# ArchitectOS Intent Router v71
# Preference Awareness + Request Classification
# ==========================================================


class IntentRouterV71:


    VERSION = "71.0"



    def __init__(self):

        print(
            "🧠 INTENT ROUTER v71 ONLINE"
        )



    def classify(
        self,
        message
    ):


        text = (
            message or ""
        ).lower()



        # ==================================================
        # PREFERENCE GUARD
        # Personal taste is NOT a design request
        # ==================================================

        preference_words = [

            "دوست دارم",
            "علاقه دارم",
            "علاقه‌مندم",
            "پسند من",
            "سبک مورد علاقه",
            "ترجیح میدم",
            "ترجیح می‌دهم",
            "i like",
            "my favorite"

        ]


        if any(
            word in text
            for word in preference_words
        ):


            return "chat"




        # ==================================================
        # IMAGE
        # ==================================================

        image_words = [

            "image",
            "تصویر",
            "عکس",
            "نقاشی",
            "draw",
            "generate image"

        ]


        if any(
            word in text
            for word in image_words
        ):

            return "image"




        # ==================================================
        # DESIGN REQUEST
        # ==================================================

        design_words = [

            "طراحی کن",
            "طراحی",
            "معماری کن",
            "معماری",
            "ویلا طراحی",
            "ساختمان طراحی",
            "نقشه",
            "پلان",
            "plan",
            "design",
            "floor"

        ]


        action_words = [

            "کن",
            "بده",
            "بساز",
            "ایجاد",
            "create",
            "make"

        ]



        has_design = any(

            word in text

            for word in design_words

        )


        has_action = any(

            word in text

            for word in action_words

        )



        if has_design and (
            has_action
            or "طراحی" in text
        ):

            return "design"




        # ==================================================
        # MEMORY
        # ==================================================

        memory_words = [

            "یادت",
            "remember",
            "memory"

        ]


        if any(
            word in text
            for word in memory_words
        ):

            return "memory"




        return "chat"





# ==========================================================
# SINGLETON
# ==========================================================


intent_router = IntentRouterV71()