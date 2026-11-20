class SpatialLayoutEngine:

    def __init__(self, unit_size=4):
        self.unit = unit_size

        print(
            "SPATIAL ENGINE INIT UNIT:",
            unit_size
        )

    # ======================
    # MAIN ENTRY (STEP 42 V2)
    # ======================
    def layout(self, graph, floor_name, width=12, height=10):

        nodes = {}

        grid_x = 0
        grid_y = 0

        max_x = width
        max_y = height

        used_positions = []


        print(
            "NODE COUNT:",
            len(graph),
            "AVAILABLE AREA:",
            width * height,
            "UNIT AREA:",
            self.unit * self.unit
        )

        # helper: check collision
        def is_free(x, y, w, h):
            for ux, uy, uw, uh in used_positions:
                if not (x + w <= ux or ux + uw <= x or y + h <= uy or uy + uh <= y):
                    return False
            return True

        # ======================
        # CORE PLACEMENT FIRST
        # ======================
        core_node = None

        for n in graph:
            if "Core" in n:
                core_node = n
                break

        if core_node:
            cx = (
                int(max_x / self.unit / 2)
                * self.unit
            )

            cy = (
                int(max_y / self.unit / 2)
                * self.unit
            )

            nodes[core_node] = {
                "x": cx,
                "y": cy,
                "w": self.unit,
                "h": self.unit,
                "connections": graph[core_node]
            }

            used_positions.append((cx, cy, self.unit, self.unit))

        # ======================
        # PLACE CONNECTED NODES AROUND CORE
        # ======================
        def place_around(base_x, base_y, node, edges, radius=1):

            directions = [
                (0, -1), (1, 0), (0, 1), (-1, 0),
                (1, -1), (-1, -1), (1, 1), (-1, 1)
            ]

            for dx, dy in directions:

                x = base_x + dx * radius * self.unit * 2
                y = base_y + dy * radius * self.unit * 2

                if (
                    x < 0
                    or y < 0
                    or x + self.unit > max_x
                    or y + self.unit > max_y
                ):
                    continue

                if is_free(x, y, self.unit, self.unit):

                    nodes[node] = {
                        "x": x,
                        "y": y,
                        "w": self.unit,
                        "h": self.unit,
                        "connections": edges
                    }

                    used_positions.append((x, y, self.unit, self.unit))
                    return True

            return False

        # ======================
        # PLACE ALL NODES
        # ======================
        for node, edges in graph.items():

            if node in nodes:
                continue

            # ======================
            # EXTERNAL SPACE HANDLER
            # ======================

            if (
                "Roof-Terrace" in node
                or "Terrace" in node
                or "Balcony" in node
            ):

                nodes[node] = {

                    "x": 0,

                    "y": height,

                    "w": self.unit,

                    "h": self.unit,

                    "connections": edges,

                    "external": True

                }

                print(
                    "EXTERNAL SPACE PLACED:",
                    node
                )

                continue

            # ======================
            # EXTERNAL SPACES
            # ======================

            if (
                "Roof-Terrace" in node
                or "Terrace" in node
                or "Balcony" in node
            ):

                nodes[node] = {

                    "x": 0,
                    "y": height,
                    "w": self.unit,
                    "h": self.unit,
                    "connections": edges,
                    "external": True

                }

                continue

            placed = False

            # try place near connected nodes
            for conn in edges:

                if conn in nodes:

                    base = nodes[conn]

                    placed = place_around(
                        base["x"],
                        base["y"],
                        node,
                        edges
                    )

                    if placed:
                        break


            print(
                "PLACEMENT STATUS:",
                node,
                "CONNECTED:",
                edges,
                "USED POSITIONS:",
                used_positions
            )

            # fallback grid placement
            if not placed:

                print(
                    "FALLBACK PLACEMENT:",
                    node,
                    "GRID:",
                    grid_x,
                    grid_y
                )


                attempts = 0

                while attempts < 1000:

                    attempts += 1


                    x = grid_x * self.unit
                    y = grid_y * self.unit


                    if x > max_x:

                        grid_x = 0
                        grid_y += 1
                        continue


                    if (
                        x + self.unit > max_x
                        or y + self.unit > max_y
                    ):

                        grid_x += 1
                        continue


                    if is_free(
                        x,
                        y,
                        self.unit,
                        self.unit
                    ):

                        nodes[node] = {

                            "x": x,
                            "y": y,
                            "w": self.unit,
                            "h": self.unit,
                            "connections": edges

                        }


                        used_positions.append(
                            (
                                x,
                                y,
                                self.unit,
                                self.unit
                            )
                        )

                        placed = True
                        break


                    grid_x += 1



                if not placed:

                    print(
                        "PLACEMENT FAILED:",
                        node,
                        "LEVEL:",
                        floor_name
                    )

                    nodes[node] = {

                        "x": 0,

                        "y": 0,

                        "w": self.unit,

                        "h": self.unit,

                        "connections": edges,

                        "unplaced": True,

                        "placement_failed": True

                    }

        print(
            "\n====== SPATIAL NODE VALIDATION DEBUG ======"
        )


        for name, node in nodes.items():

            print(
                name,
                {
                    "x": node.get("x"),
                    "y": node.get("y"),
                    "w": node.get("w"),
                    "h": node.get("h"),
                    "unplaced": node.get("unplaced")
                }
            )


        print(
            "============================================"
        )

        print(
            "\n====== SPATIAL NODE BEFORE OUTPUT CHECK ======"
        )

        for name, node in nodes.items():

            print(
                name,
                {
                    "x": node.get("x"),
                    "y": node.get("y"),
                    "w": node.get("w"),
                    "h": node.get("h"),
                    "unplaced": node.get("unplaced")
                }
            )

        print(
            "=============================================="
        )

        # ======================
        # OUTPUT
        # ======================

        print(
            "\n====== SPATIAL FINAL BOUNDS CHECK ======"
        )

        print(
            "LEVEL:",
            floor_name
        )

        print(
            "WIDTH:",
            width
        )

        print(
            "HEIGHT:",
            height
        )


        invalid_nodes = []


        for name, node in nodes.items():

            if node.get(
                "external",
                False
            ):

                print(
                    "SKIP EXTERNAL BOUNDS:",
                    name
                )

                continue


            x = node.get(
                "x"
            )

            y = node.get(
                "y"
            )

            w = node.get(
                "w"
            )

            h = node.get(
                "h"
            )


            if None in [
                x,
                y,
                w,
                h
            ]:

                print(
                    "INVALID NODE DATA:",
                    name,
                    node
                )

                invalid_nodes.append(
                    name
                )

                continue



            if (
                x + w > width
                or
                y + h > height
            ):

                print(
                    "OUT OF BOUNDS:",
                    name,
                    x,
                    y,
                    w,
                    h
                )


        print(
            "INVALID NODES:",
            invalid_nodes
        )


        print(
            "========================================"
        )


        print(
            "\n====== SPATIAL NODE FINAL CONTRACT ======"
        )


        for name, node in nodes.items():

            print(
                name,
                {
                    "x": node.get("x"),
                    "y": node.get("y"),
                    "w": node.get("w"),
                    "h": node.get("h"),
                    "unplaced": node.get(
                        "unplaced",
                        False
                    )
                }
            )


        print(
            "TOTAL NODES:",
            len(nodes)
        )


        print(
            "UNPLACED:",
            [
                name
                for name, node in nodes.items()
                if node.get(
                    "unplaced",
                    False
                )
            ]
        )


        print(
            "========================================"
        )

        print(
            "\n====== FINAL SPATIAL INVALID CHECK ======"
        )


        for name, node in nodes.items():

            if None in [
                node.get("x"),
                node.get("y"),
                node.get("w"),
                node.get("h")
            ]:

                print(
                    "INVALID NODE SOURCE:",
                    name,
                    node
                )


        print(
            "=========================================="
        )

        print("\n====== SPATIAL RETURN NODE CHECK ======")

        for name, node in nodes.items():
            print(
                "RETURN NODE:",
                 name,
                node.get("x"),
                node.get("y"),
                node.get("w"),
                node.get("h")
            )

        print("======================================")


        return {
            "floor": floor_name,
            "width": width,
            "height": height,
            "unit": self.unit,
            "nodes": nodes
        }