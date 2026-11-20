class GeometryAdapter:
    """
    ArchitectOS Unified Geometry Adapter
    Single source of geometry for every BIM Engine
    """

    def __init__(self, geometry_result):
        self.geometry = geometry_result or {}

    def get_walls(self):
        return self.geometry.get("walls", [])

    def get_slabs(self):
        return self.geometry.get("slabs", [])

    def get_columns(self):
        return self.geometry.get("columns", [])

    def get_beams(self):
        return self.geometry.get("beams", [])

    def get_roofs(self):
        return self.geometry.get("roofs", [])

    def get_stairs(self):
        return self.geometry.get("stairs", [])

    def get_openings(self):
        return self.geometry.get("openings", [])

    def get_rooms(self):
        return self.geometry.get("rooms", [])

    def get_mesh(self, element):
        return element.get("mesh")

    def get_bbox(self, element):
        return element.get("bbox")

    def get_transform(self, element):
        return {
            "location": element.get("location"),
            "rotation": element.get("rotation"),
            "scale": element.get("scale"),
        }

    def get_property(self, element, key, default=None):
        return element.get(key, default)