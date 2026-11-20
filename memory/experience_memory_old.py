# ==========================================================
# ArchitectOS v61
# Experience Memory Engine
# ==========================================================


import json
import os
from datetime import datetime


class ExperienceMemory:


    def __init__(self):

        self.file = os.path.join(
            os.path.dirname(__file__),
            "project_history.json"
        )

        self.memory = self.load()



    # ======================
    # LOAD MEMORY
    # ======================

    def load(self):

        if not os.path.exists(self.file):

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



    # ======================
    # SAVE MEMORY
    # ======================

    def save(self):

        with open(
            self.file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                self.memory,
                f,
                indent=4,
                ensure_ascii=False
            )



    # ======================
    # STORE EXPERIENCE
    # ======================

    def add_project(
        self,
        project_data
    ):


        experience = {

            "timestamp":
                str(datetime.now()),


            "project":
                project_data.get(
                    "project",
                    {}
                ),


            "validation":
                project_data.get(
                    "validation",
                    {}
                ),


            "decision":
                project_data.get(
                    "decision_v83",
                    {}
                ),


            "lessons":
                project_data.get(
                    "decision_v83",
                    {}
                ).get(
                    "recommendations",
                    []
                )

        }


        self.memory.append(
            experience
        )


        self.save()


        return {

            "status":
                "MEMORY_STORED",


            "projects":
                len(self.memory)

        }



    # ======================
    # RETRIEVE EXPERIENCE
    # ======================

    def get_recent(
        self,
        limit=5
    ):


        return self.memory[-limit:]



    # ======================
    # MEMORY SUMMARY
    # ======================

    def summary(self):

        return {

            "engine":
                "ARCHITECTOS_EXPERIENCE_MEMORY_V61",


            "projects":
                len(self.memory),


            "status":
                "ONLINE"

        }