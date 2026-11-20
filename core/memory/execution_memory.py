# ==========================================================
# ArchitectOS Execution Memory v1.0
# Runtime / Agent / GOD CORE Memory Store
# ==========================================================

import json
import os
import time


class ExecutionMemory:

    MAX_RECORDS = 100


    def __init__(self):

        self.file = os.path.join(
            os.path.dirname(__file__),
            "execution_memory.json"
        )

        self.data = self.load()

        print(
            "EXECUTION MEMORY v1.0 ONLINE"
        )


    # ======================================================
    # LOAD
    # ======================================================

    def load(self):

        if not os.path.exists(self.file):
            return []


        try:

            with open(
                self.file,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

                if isinstance(data, list):
                    return data


        except Exception:
            pass


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
    # STORE EXECUTION
    # ======================================================

    def store(
        self,
        engine,
        result
    ):

        record = {

            "engine": engine,

            "summary": self.summarize(
                result
            ),

            "timestamp": time.time()

        }


        self.data.append(
            record
        )


        if len(self.data) > self.MAX_RECORDS:

            self.data = self.data[
                -self.MAX_RECORDS:
            ]


        self.save()

        return record



    # ======================================================
    # SUMMARY
    # ======================================================

    def summarize(
        self,
        result
    ):

        try:

            return {

                "type":
                    type(result).__name__,


                "size":
                    len(str(result)),


                "status":
                    result.get("status")
                    if isinstance(result, dict)
                    else None

            }


        except Exception:

            return {

                "type":
                    "unknown"

            }



    # ======================================================
    # READ
    # ======================================================

    def history(
        self,
        limit=20
    ):

        return self.data[
            -limit:
        ]



execution_memory = ExecutionMemory()