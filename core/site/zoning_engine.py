class ZoningEngine:

    def __init__(self, setback_front=3, setback_back=2, setback_side=1.5):
        self.front = setback_front
        self.back = setback_back
        self.side = setback_side

    # ======================
    # MAIN FUNCTION
    # ======================
    def compute(self, site):

        """
        site format:
        {
            "polygon": [(x,y), (x,y), ...],  # can be irregular
            "street_side": "south"
        }
        """

        poly = site["polygon"]
        street = site.get("street_side", "south")

        # ======================
        # 1. NORMALIZE SITE
        # ======================
        bounds = self._bounding_box(poly)

        # ======================
        # 2. BUILD SETBACK ENVELOPE
        # ======================
        envelope = self._apply_setbacks(bounds, street)

        # ======================
        # 3. BUILDABLE AREA (INTERSECTION LOGIC)
        # ======================
        buildable = self._clip_polygon(poly, envelope)

        # ======================
        # 4. ORIENTATION LOGIC
        # ======================
        orientation = self._compute_orientation(street)

        return {
            "raw_site": poly,
            "bounds": bounds,
            "setback_envelope": envelope,
            "buildable_area": buildable,
            "orientation": orientation
        }

    # ======================
    # BOUNDING BOX
    # ======================
    def _bounding_box(self, poly):

        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]

        return {
            "min_x": min(xs),
            "max_x": max(xs),
            "min_y": min(ys),
            "max_y": max(ys)
        }

    # ======================
    # SETBACK ENGINE
    # ======================
    def _apply_setbacks(self, b, street):

        if street == "south":
            return {
                "x1": b["min_x"] + self.side,
                "x2": b["max_x"] - self.side,
                "y1": b["min_y"] + self.front,
                "y2": b["max_y"] - self.back
            }

        if street == "north":
            return {
                "x1": b["min_x"] + self.side,
                "x2": b["max_x"] - self.side,
                "y1": b["min_y"] + self.back,
                "y2": b["max_y"] - self.front
            }

        # fallback
        return {
            "x1": b["min_x"] + self.side,
            "x2": b["max_x"] - self.side,
            "y1": b["min_y"] + self.side,
            "y2": b["max_y"] - self.side
        }

    # ======================
    # POLYGON CLIPPING (SIMPLIFIED)
    # ======================
    def _clip_polygon(self, poly, env):

        clipped = []

        for x, y in poly:

            if (env["x1"] <= x <= env["x2"] and
                env["y1"] <= y <= env["y2"]):

                clipped.append((x, y))

        return clipped

    # ======================
    # ORIENTATION ENGINE
    # ======================
    def _compute_orientation(self, street):

        return {
            "main_entrance": street,
            "building_face": "opposite_to_" + street
        }