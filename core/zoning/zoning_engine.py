class ZoningEngine:

    def __init__(self):
        pass

    # ======================
    # MAIN RULE EVALUATION
    # ======================
    def evaluate(self, site, program):

        rules = {
            "max_coverage": 0.6,   # 60% footprint
            "front_setback": 2.0,
            "side_setback": 1.5,
            "rear_setback": 2.0,
            "max_height_m": 12
        }

        footprint_area = self._calc_footprint(site)

        max_allowed = self._site_area(site) * rules["max_coverage"]

        zoning_result = {
            "allowed": footprint_area <= max_allowed,
            "footprint": footprint_area,
            "max_allowed": max_allowed,
            "violations": []
        }

        if footprint_area > max_allowed:
            zoning_result["violations"].append("COVERAGE_EXCEEDED")

        return zoning_result

    # ======================
    # HELPERS
    # ======================
    def _site_area(self, site):
        if site["type"] == "rect":
            w, h = site["width"], site["height"]
            return w * h

        if site["type"] == "polygon":
            return self._polygon_area(site["points"])

        return 0

    def _polygon_area(self, pts):
        # Shoelace formula
        area = 0
        n = len(pts)

        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            area += x1 * y2 - x2 * y1

        return abs(area) / 2

    def _calc_footprint(self, site):
        # placeholder → بعداً از STEP 42 میاد
        return site.get("footprint", 50)