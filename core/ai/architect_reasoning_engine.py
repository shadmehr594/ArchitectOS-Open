class ArchitectReasoningEngine:

    def __init__(self):

        self.rules = {
            "max_corridor_ratio": 0.25,
            "min_room_area": 9,
            "max_aspect_ratio": 3.5
        }

    # ======================
    # MAIN REASONING ENTRY
    # ======================
    def analyze(self, bim, structure, zoning, loads):

        report = {
            "score": 100,
            "issues": [],
            "suggestions": []
        }

        # ======================
        # 1. SPACE QUALITY CHECK
        # ======================
        room_issue = self._check_rooms(bim)
        report["issues"] += room_issue["issues"]
        report["score"] -= room_issue["penalty"]

        # ======================
        # 2. STRUCTURAL LOGIC CHECK
        # ======================
        structure_issue = self._check_structure(structure)
        report["issues"] += structure_issue["issues"]
        report["score"] -= structure_issue["penalty"]

        # ======================
        # 3. LOAD SAFETY CHECK
        # ======================
        load_issue = self._check_loads(loads)
        report["issues"] += load_issue["issues"]
        report["score"] -= load_issue["penalty"]

        # ======================
        # 4. ZONING COMPLIANCE
        # ======================
        if not zoning.get("valid", True):
            report["issues"].append("Zoning violations detected")
            report["score"] -= 20

        # ======================
        # FINAL SUGGESTIONS
        # ======================
        if report["score"] < 70:
            report["suggestions"].append("Reduce building footprint or redistribute rooms")

        if report["score"] < 50:
            report["suggestions"].append("Major redesign required")

        return report

    # ======================
    # ROOM ANALYSIS
    # ======================
    def _check_rooms(self, bim):

        issues = []
        penalty = 0

        for room in bim.get("rooms", []):

            area = room["w"] * room["h"]

            if area < self.rules["min_room_area"]:
                issues.append(f"Room too small: {room['name']}")
                penalty += 10

            ratio = max(room["w"], room["h"]) / max(1, min(room["w"], room["h"]))

            if ratio > self.rules["max_aspect_ratio"]:
                issues.append(f"Bad proportions: {room['name']}")
                penalty += 5

        return {"issues": issues, "penalty": penalty}

    # ======================
    # STRUCTURE CHECK
    # ======================
    def _check_structure(self, structure):

        issues = []
        penalty = 0

        if len(structure.get("columns", [])) == 0:
            issues.append("No structural columns found")
            penalty += 50

        if len(structure.get("beams", [])) < 3:
            issues.append("Weak structural connectivity")
            penalty += 20

        return {"issues": issues, "penalty": penalty}

    # ======================
    # LOAD CHECK
    # ======================
    def _check_loads(self, loads):

        issues = []
        penalty = 0

        for col in loads.get("columns", []):

            if col["axial_load_kN"] > 250:
                issues.append("Overloaded column detected")
                penalty += 15

        for beam in loads.get("beams", []):

            if beam["load_kN"] > 300:
                issues.append("Overloaded beam detected")
                penalty += 15

        return {"issues": issues, "penalty": penalty}