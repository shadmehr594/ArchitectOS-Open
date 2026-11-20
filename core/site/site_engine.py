import math


class SiteEngine:

    # ======================
    # MAIN ENTRY
    # ======================
    def load(self, site: dict):

        site_type = site.get("type", "rect")

        if site_type == "rect":
            return self._rect(site)

        if site_type == "polygon":
            return self._polygon(site)

        if site_type == "utm":
            return self._utm(site)

        if site_type == "dxf":
            return self._dxf(site)

        raise ValueError(f"Unsupported site type: {site_type}")

    # ======================
    # RECT SITE (fallback)
    # ======================
    def _rect(self, site):

        width = site.get("width", 12)
        height = site.get("height", 10)

        return {
            "type": "rect",
            "bounds": (0, 0, width, height),
            "street_edge": site.get("street_edge", "south"),
            "buildable_area": (0, 0, width, height),
            "coverage_limit": site.get("coverage", 0.6)
        }

    # ======================
    # POLYGON SITE (REAL LAND)
    # ======================
    def _polygon(self, site):

        points = site["points"]

        return {
            "type": "polygon",
            "points": points,
            "bbox": self._bbox(points),
            "street_edge": self._detect_street(points),
            "buildable_area": self._offset_polygon(points, site.get("setback", 1.5)),
            "coverage_limit": site.get("coverage", 0.6)
        }

    # ======================
    # UTM SITE (REAL WORLD)
    # ======================
    def _utm(self, site):

        zone = site.get("zone", 40)

        return {
            "type": "utm",
            "zone": zone,
            "easting": site["easting"],
            "northing": site["northing"],
            "local_xy": self._utm_to_local(site),
            "street_edge": "auto-detected",
            "buildable_area": "requires_projection_step",
            "coverage_limit": site.get("coverage", 0.6)
        }

    # ======================
    # DXF / CAD IMPORT (STEP 47 READY HOOK)
    # ======================
    def _dxf(self, site):

        # placeholder for future ezdxf integration
        return {
            "type": "dxf",
            "source": site.get("file"),
            "layers": "parsed_layers_placeholder",
            "points": "extracted_polylines_placeholder",
            "bbox": "computed_from_dxf",
            "buildable_area": "requires_setback_engine",
            "coverage_limit": site.get("coverage", 0.6)
        }

    # ======================
    # GEOMETRY HELPERS
    # ======================
    def _bbox(self, points):

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]

        return {
            "min_x": min(xs),
            "max_x": max(xs),
            "min_y": min(ys),
            "max_y": max(ys)
        }

    # ======================
    # STREET DETECTION
    # ======================
    def _detect_street(self, points):

        min_y = min(p[1] for p in points)

        return {
            "edge": "south",
            "y": min_y
        }

    # ======================
    # POLYGON OFFSET (SIMPLIFIED)
    # ======================
    def _offset_polygon(self, points, margin=1.5):

        # real version = shapely buffer (future upgrade)
        return {
            "offset_margin": margin,
            "status": "simulated_buildable_area",
            "note": "replace with geometric buffering in STEP 47"
        }

    # ======================
    # UTM → LOCAL XY (HOOK)
    # ======================
    def _utm_to_local(self, site):

        # simplified projection (real version → pyproj)
        return {
            "x": site["easting"] % 1000,
            "y": site["northing"] % 1000,
            "note": "placeholder projection"
        }