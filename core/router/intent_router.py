# ==========================================================
# ArchitectOS Intent Router v1
# Unified Intent Classification Layer
# Core Platform v26
# ==========================================================


class IntentRouter:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧭 INTENT ROUTER v1 ONLINE"
        )



    # ======================================================
    # ROUTE
    # ======================================================

    def route(
        self,
        text,
        image=None,
        context=None
    ):


        text = (
            text or ""
        ).lower()

        context = context or {}
        state = context.get(
            "conversation_state",
            {}
        )


        # ==================================================
        # STATE BASED IMAGE EDIT
        # ==================================================

        if (
            state.get("waiting_image_edit", False)
            and text
        ):

            edit_state_words = [

                "تغییر",
                "اصلاح",
                "ویرایش",
                "اضافه",
                "حذف",
                "نما",
                "facade",
                "modify",
                "edit"

            ]

            if any(
                w in text
                for w in edit_state_words
            ):

                return {

                    "intent":
                        "image",

                    "mode":
                        "edit"

                }



        # ==================================================
        # IMAGE EDIT
        # ==================================================

        edit_words = [

            "edit",
            "modify",
            "change",
            "renovate",
            "modernize",
            "facade",
            "نمای",
            "مدرن کن",
            "تغییر بده",
            "اصلاح کن"

        ]


        if image and any(
            w in text
            for w in edit_words
        ):


            return {

                "intent":
                    "image",

                "mode":
                    "edit"

            }



        # ==================================================
        # IMAGE GENERATE
        # ==================================================

        image_words = [

            "image",
            "render",
            "draw",
            "generate",
            "تصویر",
            "رندر",
            "بساز"

        ]


        if any(
            w in text
            for w in image_words
        ):


            return {

                "intent":
                    "image",

                "mode":
                    "generate"

            }



        # ==================================================
        # VIDEO
        # ==================================================

        video_words = [

            "video",
            "camera",
            "fly",
            "animation",
            "حرکت دوربین",
            "ویدیو"

        ]


        if any(
            w in text
            for w in video_words
        ):


            return {

                "intent":
                    "video",

                "mode":
                    "camera_motion"

            }



        # ==================================================
        # DESIGN
        # ==================================================

        design_words = [

            "villa",
            "house",
            "building",
            "design",
            "architecture",
            "plan",
            "floor",
            "ویلا",
            "ساختمان",
            "طراحی",
            "معماری"

        ]


        if any(
            w in text
            for w in design_words
        ):


            return {

                "intent":
                    "design",

                "mode":
                    "create"

            }



        # ==================================================
        # MEMORY
        # ==================================================

        memory_words = [

            "remember",
            "memory",
            "history",
            "یادته",
            "حافظه"

        ]


        if any(
            w in text
            for w in memory_words
        ):


            return {

                "intent":
                    "memory",

                "mode":
                    "recall"

            }



        # ==================================================
        # DEFAULT CHAT
        # ==================================================

        return {

            "intent":
                "chat",

            "mode":
                "conversation"

        }



# singleton

intent_router = IntentRouter()