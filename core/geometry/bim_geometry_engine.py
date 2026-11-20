class BIMGeometryEngine:

    def __init__(self, wall_height=3.0):
        self.wall_height = wall_height

    # ======================
    # MAIN ENTRY
    # ======================
    def build(self, spatial):

        geometry = {
            "walls": [],
            "floors": [],
            "rooms": []
        }

        for floor_name, floor_data in spatial.items():

            nodes = floor_data.get("nodes", {})

            # ======================
            # ROOMS (VOLUMES)
            # ======================
            for node, props in nodes.items():

                geometry["rooms"].append({
                    "name": node,
                    "x": props["x"],
                    "y": props["y"],
                    "z": 0,
                    "w": props["w"],
                    "h": props["h"],
                    "height": self.wall_height
                })

                # ======================
                # WALL GENERATION
                # ======================
                walls = self._generate_walls(props, node)
                geometry["walls"].extend(walls)

                print("GENERATED WALLS:")
                for w in walls:
                    print(w["start"], "---->", w["end"])

            # ======================
            # FLOOR SLAB
            # ======================
            geometry["floors"].append({
                "floor": floor_name,
                "type": "slab",
                "thickness": 0.3
            })

        return geometry

    # ======================
    # WALL GENERATOR
    # ======================
    def _generate_walls(self, props, node):

        x = props["x"]
        y = props["y"]
        w = props["w"]
        h = props["h"]

        return [
            {
                "node": node,
                "type": "wall",
                "start": (x, y),
                "end": (x + w, y),
                "height": self.wall_height
            },
            {
                "node": node,
                "type": "wall",
                "start": (x + w, y),
                "end": (x + w, y + h),
                "height": self.wall_height
            },
            {
                "node": node,
                "type": "wall",
                "start": (x + w, y + h),
                "end": (x, y + h),
                "height": self.wall_height
            },
            {
                "node": node,
                "type": "wall",
                "start": (x, y + h),
                "end": (x, y),
                "height": self.wall_height
            }
        ]