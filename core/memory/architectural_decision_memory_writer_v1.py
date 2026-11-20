# ==========================================================
# ARCHITECTURAL DECISION MEMORY WRITER V1
# ARCHITECTOS MEMORY BRIDGE
# ==========================================================


class ArchitecturalDecisionMemoryWriterV1:


    VERSION = "1.0"



    def __init__(self):

        print(
            "🧠 Architectural Decision Memory Writer v1.0 ACTIVE"
        )


        self.memory_records = []



    # ======================================================
    # WRITE DECISION MEMORY
    # ======================================================


    def write(
        self,
        decision_context
    ):


        decision = (
            decision_context.get(
                "selected_decision",
                {}
            )
        )



        memory_record = {


            "memory_type":

                "architectural_decision",



            "decision_type":

                decision.get(
                    "proposal"
                ),



            "target":

                decision.get(
                    "target"
                ),



            "priority":

                decision.get(
                    "priority"
                ),



            "confidence":

                decision.get(
                    "confidence",
                    0
                ),



            "source":

                "architectural_decision_selector"

        }



        self.memory_records.append(
            memory_record
        )



        return {


            "engine":

                "ARCHITECTURAL_DECISION_MEMORY_WRITER_V1",


            "version":

                self.VERSION,


            "memory":

                memory_record,


            "total_records":

                len(
                    self.memory_records
                ),


            "stored":

                True

        }