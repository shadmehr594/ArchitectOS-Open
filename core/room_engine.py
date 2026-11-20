class RoomEngine:

    def build_rooms(self, spatial):

        rooms = {}

        for floor_id, floor in spatial.items():

            nodes = floor.get("nodes", {})

            node_count = len(nodes)

            # ساده ولی effective heuristic
            if node_count < 10:
                room_type = "small_room"
            elif node_count < 20:
                room_type = "medium_room"
            else:
                room_type = "large_open_space"

            rooms[floor_id] = {
                "type": room_type,
                "nodes_count": node_count,
                "zones": self.detect_zones(nodes)
            }

        return rooms

    def detect_zones(self, nodes):

        zones = {
            "core": [],
            "edges": [],
            "center": []
        }

        for node_id, n in nodes.items():

            x, y = n["x"], n["y"]

            if x == 0 or y == 0:
                zones["edges"].append(node_id)

            elif x > 10 and y > 10:
                zones["center"].append(node_id)

            else:
                zones["core"].append(node_id)

        return zones