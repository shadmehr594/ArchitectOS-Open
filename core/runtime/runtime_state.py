# ==========================================================
# ArchitectOS Runtime State Manager v1
# Persistent Runtime Mode Storage
# ==========================================================


import json
from pathlib import Path



STATE_FILE = Path(
    "core/runtime/runtime_state.json"
)



class RuntimeStateManager:


    def __init__(self):

        self.state_file = STATE_FILE



    # ======================================================
    # LOAD
    # ======================================================

    def load_mode(self):


        if not self.state_file.exists():

            return "hybrid"



        try:

            data = json.loads(
                self.state_file.read_text(
                    encoding="utf-8"
                )
            )


            return data.get(
                "mode",
                "hybrid"
            )


        except Exception:


            return "hybrid"



    # ======================================================
    # SAVE
    # ======================================================

    def save_mode(
        self,
        mode
    ):


        data = {

            "mode":
                mode

        }


        self.state_file.write_text(

            json.dumps(
                data,
                indent=4
            ),

            encoding="utf-8"

        )



# ==========================================================
# GLOBAL INSTANCE
# ==========================================================


runtime_state = RuntimeStateManager()