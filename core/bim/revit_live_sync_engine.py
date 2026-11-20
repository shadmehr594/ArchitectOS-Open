import time
import json


class RevitLiveSyncEngine:

    def __init__(self, design_engine):

        self.design_engine = design_engine

        self.last_revit_state = None
        self.last_ai_state = None

    # ======================
    # MAIN LOOP (LIVE SYNC)
    # ======================
    def run_live_sync(self):

        while True:

            # STEP 1 - READ FROM REVIT
            revit_state = self._read_revit()

            # STEP 2 - DETECT CHANGES FROM REVIT
            if self._changed_from_revit(revit_state):

                ai_update = self._convert_revit_to_ai(revit_state)

                self.last_ai_state = ai_update

            # STEP 3 - AI SIDE UPDATE
            ai_state = self.design_engine.execute(
                self.last_ai_state or {}
            )

            # STEP 4 - PUSH BACK TO REVIT
            if self._changed_from_ai(ai_state):

                self._push_to_revit(ai_state)

            self.last_revit_state = revit_state
            self.last_ai_state = ai_state

            time.sleep(1)

    # ======================
    # REVIT READER (SIMULATED API)
    # ======================
    def _read_revit(self):

        # واقعی: Revit API / IFC / pyRevit hook
        return {
            "walls": [
                {"id": 1, "x": 10, "y": 20},
                {"id": 2, "x": 30, "y": 20}
            ],
            "floors": 3,
            "updated_at": time.time()
        }

    # ======================
    # CHANGE DETECTION
    # ======================
    def _changed_from_revit(self, new_state):

        return new_state != self.last_revit_state

    def _changed_from_ai(self, ai_state):

        return ai_state != self.last_ai_state

    # ======================
    # REVIT → AI CONVERTER
    # ======================
    def _convert_revit_to_ai(self, revit_state):

        return {
            "type": "revit_import",
            "floors": revit_state.get("floors"),
            "spatial_seed": revit_state.get("walls")
        }

    # ======================
    # AI → REVIT PUSH
    # ======================
    def _push_to_revit(self, ai_state):

        payload = self._convert_ai_to_revit(ai_state)

        # واقعی: Revit API call / Dynamo / IFC export
        print("📤 PUSH TO REVIT:", json.dumps(payload, indent=2))

    # ======================
    # CONVERTER
    # ======================
    def _convert_ai_to_revit(self, ai_state):

        return {
            "walls": ai_state.get("spatial"),
            "structure": ai_state.get("structure"),
            "floors": ai_state.get("graph")
        }