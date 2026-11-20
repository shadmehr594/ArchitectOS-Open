# ==========================================================
# ArchitectOS Profile Extractor v7
# User Message -> Long Term Profile Facts
# UTF-8 Clean Version
# ==========================================================


import re
import time



class ProfileExtractor:


    def __init__(
        self,
        profile_memory=None
    ):

        self.profile_memory = profile_memory

        print(
            "👤 PROFILE EXTRACTOR v7 ONLINE"
        )



    def extract(
        self,
        message
    ):


        original = str(message)

        text = original.lower()


        profile = {}



        # ==================================================
        # USER IDENTITY
        # ==================================================

        name_patterns = [

            # من مهدی هستم
            r"من\s+([^\s]+)\s+(?:هستم|هست|میباشم|می‌باشم)",

            # من اسمم مهدی هست
            r"من\s+اسمم\s+([^\s]+)\s+(?:هست|است|میباشد|می‌باشد)",

            # اسمم مهدی است / هست
            r"اسمم\s+([^\s]+)\s+(?:است|هست|میباشد|می‌باشد)",

            # اسم من مهدی است / هست
            r"اسم\s+من\s+([^\s]+)\s+(?:است|هست|میباشد|می‌باشد)",

            # نام من مهدی است / هست
            r"نام\s+من\s+([^\s]+)\s+(?:است|هست|میباشد|می‌باشد)",

            # انگلیسی
            r"my\s+name\s+is\s+([A-Za-z]+)"

        ]



        user_name = None



        for pattern in name_patterns:


            match = re.search(
                pattern,
                original,
                re.IGNORECASE
            )


            if match:


                candidate = (
                    match.group(1)
                    .strip()
                )


                # جلوگیری از ذخیره کلمات اشتباه
                invalid_names = [

                    "کی",
                    "چی",
                    "من",
                    "یک",
                    "یه"

                ]


                if candidate.lower() not in invalid_names:


                    user_name = candidate

                    break



        if user_name:


            profile.setdefault(
                "user",
                {}
            )


            profile["user"]["name"] = user_name



        # ==================================================
        # PROJECT DETECTION
        # ==================================================

        project_words = [

            "project",
            "پروژه",
            "architectos"

        ]


        if any(
            x in text
            for x in project_words
        ):


            profile.setdefault(
                "projects",
                {}
            )


            profile["projects"]["current"] = original



        # ==================================================
        # ARCHITECTURE INTEREST
        # ==================================================

        architecture_words = [

            "معمار",
            "معماری",
            "architecture",
            "design"

        ]


        if any(
            x in text
            for x in architecture_words
        ):


            profile.setdefault(
                "interests",
                []
            )


            if "architecture" not in profile["interests"]:


                profile["interests"].append(
                    "architecture"
                )



        # ==================================================
        # FAMILY
        # ==================================================

        if (
            "فرزند" in original
            or
            "بچه" in original
        ):


            profile.setdefault(
                "family",
                {}
            )


            profile["family"]["last_note"] = original



        # ==================================================
        # FOOD
        # ==================================================

        if (
            "آشپزی" in original
            or
            "cooking" in text
        ):


            profile.setdefault(
                "food_preferences",
                {}
            )


            profile["food_preferences"]["last_note"] = original



        # ==================================================
        # METADATA
        # ==================================================

        if profile:


            profile["metadata"] = {

                "updated": time.time()

            }



        # ==================================================
        # SAVE
        # ==================================================

        if (
            profile
            and
            self.profile_memory
        ):


            self.profile_memory.update(
                profile
            )



        return profile


