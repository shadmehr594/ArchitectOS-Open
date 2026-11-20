# ==========================================================
# ArchitectOS Image Intent Router v1
# Detect Image Generation / Edit / Video Intent
# ==========================================================


class ImageIntentRouter:


    VERSION = "1.0"


    def __init__(self):

        print(
            "🖼️ IMAGE INTENT ROUTER v1 ONLINE"
        )


    # ======================================================
    # ROUTE
    # ======================================================

    def route(
        self,
        state
    ):

        state = state or {}


        prompt = (
            state.get("prompt","")
            .lower()
        )


        image = state.get(
            "image"
        )


        # ------------------------------
        # IMAGE + VIDEO
        # ------------------------------

        video_keywords = [
            "video",
            "animation",
            "camera",
            "fly",
            "orbit",
            "walkthrough",
            "حرکت",
            "ویدیو",
            "انیمیشن",
            "دوربین"
        ]


        if image and any(
            k in prompt
            for k in video_keywords
        ):

            return {

                "intent":
                    "image_video",

                "engine":
                    "wan",

                "mode":
                    "video"

            }


        # ------------------------------
        # IMAGE EDIT
        # ------------------------------

        edit_keywords = [
            "edit",
            "change",
            "modify",
            "renovate",
            "modernize",
            "improve",
            "facade",
            "تغییر",
            "بازسازی",
            "مدرن",
            "نما",
            "اصلاح"
        ]


        if image and any(
            k in prompt
            for k in edit_keywords
        ):

            return {

                "intent":
                    "image_edit",

                "engine":
                    "flux",

                "mode":
                    "edit"

            }


        # ------------------------------
        # GENERATE
        # ------------------------------

        return {

            "intent":
                "image_generate",

            "engine":
                "flux",

            "mode":
                "generate"

        }