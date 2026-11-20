import json


class RevitSyncEngine:

    def __init__(self):
        self.connected = False
        self.cache = {}

    # ======================
    # CONNECT TO REVIT (SIMULATED)
    # ======================
    def connect(self):

        # در نسخه واقعی اینجا Revit API / Add-in وصل میشه
        self.connected = True

        print("🔗 Connected to Revit BIM API")

        return self.connected

    # ======================
    # PUSH MODEL → REVIT
    # ======================
    def push_to_revit(self, bim_model):

        if not self.connected:
            raise Exception("Revit not connected")

        payload = self._convert_to_revit_format(bim_model)

        print("📤 Sending model to Revit...")

        self.cache["last_push"] = payload

        return {
            "status": "pushed",
            "elements": len(payload["elements"])
        }

    # ======================
    # PULL MODEL ← REVIT
    # ======================
    def pull_from_revit(self):

        # شبیه‌سازی داده برگشتی از Revit
        revit_data = {
            "walls": 12,
            "floors": 3,
            "columns": 24,
            "beams": 40
        }

        self.cache["last_pull"] = revit_data

        print("📥 Pulled model from Revit")

        return revit_data

    # ======================
    # CONVERSION LAYER
    # ======================
    def _convert_to_revit_format(self, bim_model):

        elements = []

        # WALLS
        for w in bim_model.get("walls", []):
            elements.append({
                "type": "Wall",
                "geometry": w
            })

        # FLOORS
        for f in bim_model.get("floors", []):
            elements.append({
                "type": "Floor",
                "data": f
            })

        # STRUCTURE
        for c in bim_model.get("columns", []):
            elements.append({
                "type": "Column",
                "location": (c["x"], c["y"], c["z"])
            })

        for b in bim_model.get("beams", []):
            elements.append({
                "type": "Beam",
                "start": b["start"],
                "end": b["end"]
            })

        return {
            "schema": "REVIT_SIMPLIFIED",
            "elements": elements
        }

    # ======================
    # SYNC LOOP
    # ======================
    def sync(self, bim_model):

        self.push_to_revit(bim_model)
        revit_state = self.pull_from_revit()

        return {
            "synced": True,
            "revit_state": revit_state
        }