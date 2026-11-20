class RevitExportEngine:

    # ======================
    # MAIN EXPORT
    # ======================
    def export(self, structure, site=None):

        columns = structure.get("columns", [])
        beams = structure.get("beams", [])
        walls = structure.get("walls", [])
        slabs = structure.get("slabs", [])

        return {
            "ifc": self.to_ifc(columns, beams, walls, slabs),
            "dxf": self.to_dxf(columns, beams, walls),
            "levels": self.build_levels(slabs),
            "revit_families": self.map_families(columns, beams, walls),
            "metadata": {
                "units": "meters",
                "source": "ArchitectOS BIM Engine"
            }
        }

    # ======================
    # IFC STRUCTURE (SIMPLIFIED)
    # ======================
    def to_ifc(self, columns, beams, walls, slabs):

        return {
            "IFCProject": {
                "elements": {
                    "IfcColumn": columns,
                    "IfcBeam": beams,
                    "IfcWall": walls,
                    "IfcSlab": slabs
                }
            }
        }

    # ======================
    # DXF EXPORT (2D SIMPLIFIED)
    # ======================
    def to_dxf(self, columns, beams, walls):

        lines = []

        # columns as points
        for c in columns:
            lines.append({
                "type": "POINT",
                "x": c["x"],
                "y": c["y"]
            })

        # beams as lines
        for b in beams:
            lines.append({
                "type": "LINE",
                "x1": b["from"]["x"],
                "y1": b["from"]["y"],
                "x2": b["to"]["x"],
                "y2": b["to"]["y"]
            })

        # walls as rectangles
        for w in walls:
            lines.append({
                "type": "RECT",
                "x": w["x"],
                "y": w["y"],
                "w": w["w"],
                "h": w["h"]
            })

        return lines

    # ======================
    # LEVEL SYSTEM (REVIT LEVELS)
    # ======================
    def build_levels(self, slabs):

        levels = []

        for i, slab in enumerate(slabs):

            levels.append({
                "name": f"Level_{i+1}",
                "elevation": i * 3.2,  # default floor height
                "slab_bounds": slab.get("bounds")
            })

        return levels

    # ======================
    # FAMILY MAPPING
    # ======================
    def map_families(self, columns, beams, walls):

        return {
            "columns": "Structural Columns - Concrete",
            "beams": "Structural Framing - Concrete Beam",
            "walls": "Basic Wall - Generic 200mm",
            "slabs": "Floor Slab - Structural Concrete"
        }