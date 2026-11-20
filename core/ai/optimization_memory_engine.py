class OptimizationMemoryEngine:


    def __init__(self):

        self.engine = (
            "ARCHITECTOS_OPTIMIZATION_MEMORY_ENGINE_V90"
        )

        self.history = []



    def store(
        self,
        before=None,
        after=None,
        changes=None,
        status=None
    ):


        # ==========================================
        # V98 COMPATIBILITY MODE
        # store(feedback_result)
        # ==========================================
        if isinstance(before, dict) and (
            after is None
            and changes is None
            and status is None
        ):

            feedback = before


            record = {

                "before":
                feedback.get(
                    "before",
                    {}
                ),


                "after":
                feedback.get(
                    "after",
                    {}
                ),


                "changes":
                feedback.get(
                    "changes",
                    []
                ),


                "status":
                feedback.get(
                    "status",
                    "FEEDBACK_STORED"
                )

            }


        # ==========================================
        # LEGACY V90 MODE
        # ==========================================
        else:

            record = {

                "before":
                before,

                "after":
                after,

                "changes":
                changes,

                "status":
                status

            }



        self.history.append(record)



        return {

            "engine":
            self.engine,


            "memory_status":
            "EXPERIENCE_STORED",


            "records":
            len(self.history),


            "record":
            record

        }



    def recall(self):


        return {

            "engine":
            self.engine,


            "history":
            self.history,


            "count":
            len(self.history)

        }