class SiteLoader:

    def load(self, site_input):

        site_type = site_input.get("type", "rect")

        if site_type == "rect":
            return self._rect(site_input)

        if site_type == "polygon":
            return self._polygon(site_input)

        if site_type == "utm":
            return self._utm(site_input)

    # ----------------------
    # RECTANGLE SITE
    # ----------------------
    def _rect(self, data):
        return {
            "type": "rect",
            "bounds": (0, 0, data["width"], data["height"])
        }

    # ----------------------
    # POLYGON SITE
    # ----------------------
    def _polygon(self, data):
        points = data["points"]

        return {
            "type": "polygon",
            "points": points,
            "bbox": self._bbox(points)
        }

    # ----------------------
    # UTM SITE (IMPORTANT FOR YOU)
    # ----------------------
    def _utm(self, data):
        return {
            "type": "utm",
            "zone": data.get("zone", 40),
            "easting": data["easting"],
            "northing": data["northing"]
        }

    # ----------------------
    # BOUNDING BOX
    # ----------------------
    def _bbox(self, points):
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]

        return {
            "min_x": min(xs),
            "max_x": max(xs),
            "min_y": min(ys),
            "max_y": max(ys)
        }