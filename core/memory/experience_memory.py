# ==========================================================
# ArchitectOS Experience Memory v23.1
# Project Experience Storage
# ==========================================================


import json
import os
import time



class ExperienceMemory:


    def __init__(self):

        self.file = os.path.join(
            os.path.dirname(__file__),
            "experience_memory.json"
        )

        self.data = self.load()



    # ======================================================
    # LOAD
    # ======================================================

    def load(self):

        if not os.path.exists(
            self.file
        ):

            return []


        try:

            with open(
                self.file,
                "r",
                encoding="utf-8"
            ) as f:

                return json.load(f)


        except:

            return []



    # ======================================================
    # SAVE
    # ======================================================

    def save(self):

        with open(
            self.file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                self.data,
                f,
                ensure_ascii=False,
                indent=2
            )



    # ======================================================
    # STORE EXPERIENCE
    # ======================================================

    def store(
        self,
        project,
        analysis
    ):


        item = {

            "project":
                project,

            "analysis":
                analysis,

            "timestamp":
                time.time()

        }


        self.data.append(
            item
        )


        self.save()


        return item



    # ======================================================
    # RETRIEVE
    # ======================================================

    def retrieve_best(
        self
    ):

        return self.data[-10:]



    # ======================================================
    # SEARCH
    # ======================================================

    def search(
        self,
        keyword
    ):

        result = []


        for item in self.data:

            text = str(
                item
            ).lower()


            if str(keyword).lower() in text:

                result.append(
                    item
                )


        return result



# singleton

experience_memory = ExperienceMemory()