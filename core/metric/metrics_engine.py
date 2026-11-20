class MetricsEngine:

    def calculate(self, site, spatial, floors):

        site_area = self._site_area(site)
        footprint = self._estimate_footprint(spatial)
        gfa = self._estimate_gfa(spatial)

        coverage = footprint / site_area if site_area else 0

        return {
            "site_area": site_area,
            "footprint": footprint,
            "coverage": round(coverage, 3),
            "gross_floor_area": gfa,
            "floor_count": len(floors)
        }

    # ======================
    # SITE AREA
    # ======================
    def _site_area(self, site):

        if site["type"] == "rect":
            return site["width"] * site["height"]

        if site["type"] == "polygon":
            return self._polygon_area(site["points"])

        if site["type"] == "utm":
            # simplified engineering proxy
            return 1000

        return 0

    # ======================
    # FOOTPRINT ESTIMATION
    # ======================
    def _estimate_footprint(self, spatial):

        footprint = 0

        for floor, data in spatial.items():
            for node, props in data["nodes"].items():

                # only built spaces count
                if any(x in node for x in ["Living", "Bedroom", "Kitchen"]):
                    footprint += props["w"] * props["h"]

        return footprint

    # ======================
    # GFA (GROSS FLOOR AREA)
    # ======================
    def _estimate_gfa(self, spatial):

        total = 0

        for floor, data in spatial.items():
            for props in data["nodes"].values():
                total += props["w"] * props["h"]

        return total

    # ======================
    # POLYGON AREA (Shoelace)
    # ======================
    def _polygon_area(self, points):

        area = 0
        n = len(points)

        for i in range(n):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % n]
            area += x1 * y2 - x2 * y1

        return abs(area) / 2