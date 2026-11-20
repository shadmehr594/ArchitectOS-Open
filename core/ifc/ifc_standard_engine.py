import uuid


class IFCStandardEngine:

    def __init__(self):

        self.schema = "IFC4"

    # ======================
    # MAIN EXPORT
    # ======================
    def export(self, bim):

        model_id = str(uuid.uuid4())

        return {
            "header": self._header(model_id),
            "projects": self._project(bim),
            "sites": self._site(bim),
            "buildings": self._building(bim),
            "storeys": self._storeys(bim),
            "elements": self._elements(bim),
            "relationships": self._relationships(bim)
        }

    # ======================
    # HEADER
    # ======================
    def _header(self, model_id):

        return {
            "schema": self.schema,
            "model_id": model_id,
            "app": "ArchitectOS IFC Engine"
        }

    # ======================
    # PROJECT
    # ======================
    def _project(self, bim):

        return {
            "type": "IFCPROJECT",
            "name": "ArchitectOS_Project"
        }

    # ======================
    # SITE
    # ======================
    def _site(self, bim):

        site = bim.get("site", {})

        return {
            "type": "IFCSITE",
            "context": site
        }

    # ======================
    # BUILDING
    # ======================
    def _building(self, bim):

        return {
            "type": "IFCBUILDING",
            "name": "Main Building"
        }

    # ======================
    # STOREYS (FLOORS)
    # ======================
    def _storeys(self, bim):

        floors = bim.get("bim", {}).get("floors", [])

        return [
            {
                "type": "IFCBUILDINGSTOREY",
                "name": f.get("name"),
                "level": i
            }
            for i, f in enumerate(floors)
        ]

    # ======================
    # ELEMENTS (WALLS, SLABS, COLUMNS)
    # ======================
    def _elements(self, bim):

        elements = []

        structure = bim.get("structure", {})

        for c in structure.get("columns", []):

            elements.append({
                "type": "IFCCOLUMN",
                "x": c.get("x"),
                "y": c.get("y"),
                "z": c.get("z", 0)
            })

        for b in structure.get("beams", []):

            elements.append({
                "type": "IFCBEAM",
                "start": b.get("start"),
                "end": b.get("end")
            })

        return elements

    # ======================
    # RELATIONSHIPS
    # ======================
    def _relationships(self, bim):

        return {
            "IFCRELAGGREGATES": "project → site → building → storeys",
            "IFCRELCONTAINEDINSPATIALSTRUCTURE": "storey → elements"
        }