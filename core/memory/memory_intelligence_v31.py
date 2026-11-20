# ==========================================================
# ArchitectOS Memory Intelligence Engine v31
# Smart Memory Retrieval Layer
# ==========================================================


import time

from .user_profile_memory import user_profile_memory



class MemoryIntelligence:


    VERSION = "v31"



    def __init__(self):

        self.profile = user_profile_memory


        print(
            "🧠 MEMORY INTELLIGENCE ENGINE v31 ONLINE"
        )



    # ======================================================
    # BUILD INTELLIGENT MEMORY
    # ======================================================

    def build(
        self,
        query
    ):


        profile = self.profile.get_profile()


        text = str(
            query
        ).lower()



        result = {

            "query":
                query,

            "matched":
                {},

            "confidence":
                {},

            "timestamp":
                time.time()

        }



        # ==================================================
        # ARCHITECTURE
        # ==================================================

        architecture_words = [

            "خانه",
            "ویلا",
            "معماری",
            "اتاق",
            "ساختمان",
            "villa",
            "house",
            "architecture"

        ]


        if any(
            x in text
            for x in architecture_words
        ):


            result["matched"][

                "architecture"

            ] = profile.get(

                "preferences",
                {}

            )


            result["confidence"][

                "architecture"

            ] = 0.9




        # ==================================================
        # FOOD / COOKING
        # ==================================================

        cooking_words = [

            "غذا",
            "آشپزی",
            "دستور",
            "recipe",
            "cook"

        ]


        if any(
            x in text
            for x in cooking_words
        ):


            result["matched"][

                "cooking"

            ] = profile.get(

                "food_preferences",
                {}

            )


            result["confidence"][

                "cooking"

            ] = 0.9




        # ==================================================
        # FAMILY
        # ==================================================

        family_words = [

            "بچه",
            "فرزند",
            "خانواده",
            "family",
            "child"

        ]


        if any(
            x in text
            for x in family_words
        ):


            result["matched"][

                "family"

            ] = profile.get(

                "family",
                {}

            )


            result["confidence"][

                "family"

            ] = 0.85




        # ==================================================
        # PROJECT
        # ==================================================

        project_words = [

            "architectos",
            "پروژه",
            "project"

        ]


        if any(
            x in text
            for x in project_words
        ):


            result["matched"][

                "projects"

            ] = profile.get(

                "projects",
                {}

            )


            result["confidence"][

                "projects"

            ] = 0.95



        return result





    # ======================================================
    # TOP MEMORY
    # ======================================================

    def best_context(
        self,
        query
    ):


        data = self.build(
            query
        )


        return data.get(
            "matched",
            {}
        )





# ==========================================================
# SINGLETON
# ==========================================================


memory_intelligence = MemoryIntelligence()