class StructuralAnalysisEngine:

    def __init__(self):

        # ضرایب ساده‌شده (Engineering Approximation)
        self.dead_load_factor = 5.0   # kN/m²
        self.live_load_factor = 2.0   # kN/m²

    # ======================
    # MAIN ENTRY
    # ======================
    def analyze(self, geometry, structure):

        result = {
            "loads": {},
            "columns": [],
            "beams": [],
            "warnings": []
        }

        floor_area = self._calculate_floor_area(geometry)

        total_load = self._calculate_total_load(floor_area)

        # ======================
        # COLUMN LOAD DISTRIBUTION
        # ======================
        for col in structure.get("columns", []):

            load = self._column_load(total_load, len(structure["columns"]))

            result["columns"].append({
                "column": col,
                "axial_load_kN": load
            })

            if load > 200:
                result["warnings"].append(
                    f"⚠️ High load on column at ({col['x']}, {col['y']})"
                )

        # ======================
        # BEAM LOAD CHECK
        # ======================
        for beam in structure.get("beams", []):

            span = self._distance(beam["start"], beam["end"])

            beam_load = total_load * (span / 10)

            result["beams"].append({
                "beam": beam,
                "span": span,
                "load_kN": beam_load
            })

            if beam_load > 300:
                result["warnings"].append(
                    f"⚠️ Beam overload detected span={span}"
                )

        result["loads"]["total"] = total_load

        return result

    # ======================
    # FLOOR AREA CALC
    # ======================
    def _calculate_floor_area(self, geometry):

        area = 0

        for room in geometry.get("rooms", []):

            area += room["w"] * room["h"]

        return area

    # ======================
    # TOTAL LOAD
    # ======================
    def _calculate_total_load(self, area):

        dead = area * self.dead_load_factor
        live = area * self.live_load_factor

        return dead + live

    # ======================
    # COLUMN LOAD
    # ======================
    def _column_load(self, total_load, num_columns):

        if num_columns == 0:
            return 0

        return total_load / num_columns

    # ======================
    # DISTANCE (BEAM SPAN)
    # ======================
    def _distance(self, a, b):

        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5