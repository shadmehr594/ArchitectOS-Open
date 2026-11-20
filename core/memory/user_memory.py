# ==========================================================
# ArchitectOS User Memory v70
# Persistent User Facts
# ==========================================================


import json
import os



class UserMemory:


    def __init__(self):

        self.file = os.path.join(
            os.path.dirname(__file__),
            "user_memory.json"
        )

        self.data = self.load()



    def load(self):

        if not os.path.exists(self.file):

            return {}


        try:

            with open(
                self.file,
                "r",
                encoding="utf-8"
            ) as f:

                return json.load(f)

        except:

            return {}



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



    def update(
        self,
        facts
    ):

        self.data.update(
            facts
        )

        self.save()


        return self.data



    def get(
        self,
        key,
        default=None
    ):

        return self.data.get(
            key,
            default
        )



    def all(self):

        return self.data



user_memory = UserMemory()