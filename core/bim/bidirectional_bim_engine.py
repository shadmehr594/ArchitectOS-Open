class BidirectionalBIMEngine:

    def __init__(self):
        self.cache = {
            "model": None,
            "version": 0
        }

    # ======================
    # PUSH TO BIM (FORWARD)
    # ======================
    def push(self, bim_data):

        self.cache["model"] = bim_data
        self.cache["version"] += 1

        return {
            "status": "pushed",
            "version": self.cache["version"],
            "elements": self._count_elements(bim_data)
        }

    # ======================
    # PULL FROM BIM (REVERSE)
    # ======================
    def pull(self, external_bim):

        updated_model = self._merge_models(
            self.cache["model"],
            external_bim
        )

        self.cache["model"] = updated_model
        self.cache["version"] += 1

        return {
            "status": "synced",
            "version": self.cache["version"],
            "model": updated_model
        }

    # ======================
    # MERGE ENGINE (CORE MAGIC)
    # ======================
    def _merge_models(self, base, external):

        if not base:
            return external

        merged = base.copy()

        # merge columns
        merged["IfcColumn"] = self._merge_lists(
            base.get("IfcColumn", []),
            external.get("IfcColumn", [])
        )

        # merge beams
        merged["IfcBeam"] = self._merge_lists(
            base.get("IfcBeam", []),
            external.get("IfcBeam", [])
        )

        # merge walls
        merged["IfcWall"] = self._merge_lists(
            base.get("IfcWall", []),
            external.get("IfcWall", [])
        )

        return merged

    # ======================
    # LIST MERGE (SAFE SYNC)
    # ======================
    def _merge_lists(self, a, b):

        seen = set()
        result = []

        for item in (a + b):

            key = str(item)

            if key not in seen:
                seen.add(key)
                result.append(item)

        return result

    # ======================
    # ELEMENT COUNTER
    # ======================
    def _count_elements(self, bim_data):

        if not bim_data:
            return {}

        return {
            "columns": len(bim_data.get("IfcColumn", [])),
            "beams": len(bim_data.get("IfcBeam", [])),
            "walls": len(bim_data.get("IfcWall", []))
        }

    # ======================
    # DIFF ENGINE (WHAT CHANGED?)
    # ======================
    def diff(self, old_model, new_model):

        return {
            "added": self._difference(new_model, old_model),
            "removed": self._difference(old_model, new_model)
        }

    def _difference(self, a, b):

        result = {}

        for key in a:

            if key not in b:
                result[key] = a[key]

        return result