class RealTimeDesignEngine:

    def __init__(self, design_tool, zoning_engine, pipeline):

        self.design_tool = design_tool
        self.zoning = zoning_engine
        self.pipeline = pipeline

        # live session memory
        self.session_state = {
            "constraints": {},
            "site": None,
            "last_design": None
        }

    # ======================
    # MAIN CHAT ENTRY
    # ======================
    def chat(self, user_message: str):

        # STEP 1 - PARSE INTENT
        intent = self._parse_intent(user_message)

        # STEP 2 - UPDATE STATE (LIVE MEMORY)
        self._update_state(intent)

        # STEP 3 - REGENERATE ONLY WHAT CHANGED
        updated_design = self._incremental_update(intent)

        # STEP 4 - VALIDATE IN REAL TIME
        validation = self._validate_live(updated_design)

        # STEP 5 - RESPONSE GENERATION
        return {
            "intent": intent,
            "design": updated_design,
            "validation": validation,
            "message": self._format_response(validation)
        }

    # ======================
    # INTENT PARSER
    # ======================
    def _parse_intent(self, msg):

        msg = msg.lower()

        return {
            "change_floors": "floor" in msg,
            "change_height": "height" in msg,
            "change_units": "unit" in msg,
            "change_site": "site" in msg,
            "raw": msg
        }

    # ======================
    # STATE UPDATER
    # ======================
    def _update_state(self, intent):

        if "site" in intent["raw"]:
            self.session_state["site"] = intent

        if "height" in intent["raw"]:
            self.session_state["constraints"]["height"] = 4

        if "unit" in intent["raw"]:
            self.session_state["constraints"]["units"] = 2

    # ======================
    # INCREMENTAL UPDATE ENGINE
    # ======================
    def _incremental_update(self, intent):

        # اگر چیزی تغییر نکرده، طراحی قبلی رو نگه دار
        if not self.session_state["last_design"]:
            return self.pipeline.run(self.session_state)

        design = self.session_state["last_design"]

        # فقط بخش تغییر کرده رو بازسازی کن
        if intent["change_height"]:
            design["spatial"] = self.pipeline.rebuild_spatial(
                design["site"],
                self.session_state["constraints"].get("height", 3)
            )

        if intent["change_units"]:
            design["graph"] = self.pipeline.rebuild_graph(
                units=self.session_state["constraints"]["units"]
            )

        self.session_state["last_design"] = design

        return design

    # ======================
    # LIVE VALIDATION
    # ======================
    def _validate_live(self, design):

        site = design.get("site")
        zoning = design.get("zoning")

        if not site or not zoning:
            return {"status": "incomplete"}

        violations = []

        if zoning["valid"] is False:
            violations.append("Zoning violation detected")

        return {
            "status": "ok" if not violations else "warning",
            "violations": violations
        }

    # ======================
    # RESPONSE FORMATTER
    # ======================
    def _format_response(self, validation):

        if validation["status"] == "ok":
            return "✔ Design updated in real-time"

        return f"⚠ Issues detected: {validation.get('violations', [])}"