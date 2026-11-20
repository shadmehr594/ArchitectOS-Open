print("USING grid_engine.py StructuralGridEngine")
class StructuralGridEngine:
    """
    STEP 49 - Structural Grid Engine
    Converts buildable zone → structural grid system
    """

    def __init__(self):

        self.min_bay = 5.0
        self.max_bay = 8.0

    def _calculate_axis_grid(self, dimension):

        for bays in range(1, int(dimension) + 1):

            spacing = dimension / bays

            if (
                self.min_bay <= spacing <= self.max_bay
            ):

                return [
                    round(i * spacing, 3)
                    for i in range(bays + 1)
                ]

        # fallback
        return [
            0,
            dimension
        ]

    # ======================
    # MAIN ENTRY
    # ======================
    def generate(self, site, zoning):

        site_type = site.get("type", "rect")

        if site_type == "rect":
            return self._rect_grid(site, zoning)

        if site_type == "polygon":
            return self._polygon_grid(site, zoning)

        if site_type == "utm":
            return self._utm_grid(site, zoning)

        raise ValueError("Unsupported site type")

    # ======================
    # RECT GRID
    # ======================
    def _rect_grid(self, site, zoning):

        w, h = site["bounds"][2], site["bounds"][3]

        x_lines = self._calculate_axis_grid(w)

        y_lines = self._calculate_axis_grid(h)

        grid_points = []

        for x in x_lines:
            for y in y_lines:

                grid_points.append({
                    "id": f"G_{x}_{y}",
                    "x": x,
                    "y": y,
                    "type": "column"
                })

        return {
            "type": "rect_grid",
            "cols": cols,
            "rows": rows,
            "grid_size": self.default_grid,
            "points": grid_points
        }

    # ======================
    # POLYGON GRID
    # ======================
    def _polygon_grid(self, site, zoning):

        points = site["points"]

        bbox = site["bbox"]
        min_x, min_y = bbox["min_x"], bbox["min_y"]
        max_x, max_y = bbox["max_x"], bbox["max_y"]

        grid_points = []

        x = min_x
        i = 0

        while x <= max_x:
            y = min_y
            j = 0

            while y <= max_y:

                if self._inside_polygon(x, y, points):

                    grid_points.append({
                        "id": f"G{i}_{j}",
                        "x": x,
                        "y": y,
                        "type": "column"
                    })

                y += self.default_grid
                j += 1

            x += self.default_grid
            i += 1

        return {
            "type": "polygon_grid",
            "grid_size": self.default_grid,
            "points": grid_points
        }

    # ======================
    # UTM GRID (GIS READY)
    # ======================
    def _utm_grid(self, site, zoning):

        e = site["easting"]
        n = site["northing"]

        grid_points = []

        for i in range(-2, 3):
            for j in range(-2, 3):

                grid_points.append({
                    "id": f"UTM_{i}_{j}",
                    "easting": e + i * self.default_grid * 10,
                    "northing": n + j * self.default_grid * 10,
                    "type": "column"
                })

        return {
            "type": "utm_grid",
            "zone": site.get("zone", 40),
            "points": grid_points
        }

    # ======================
    # POINT IN POLYGON
    # ======================
    def _inside_polygon(self, x, y, poly):

        n = len(poly)
        inside = False

        p1x, p1y = poly[0]

        for i in range(n + 1):

            p2x, p2y = poly[i % n]

            if y > min(p1y, p2y):

                if y <= max(p1y, p2y):

                    if x <= max(p1x, p2x):

                        xinters = (
                            (y - p1y) * (p2x - p1x)
                        ) / (p2y - p1y + 1e-9) + p1x

                        if p1x == p2x or x <= xinters:
                            inside = not inside

            p1x, p1y = p2x, p2y

        return inside