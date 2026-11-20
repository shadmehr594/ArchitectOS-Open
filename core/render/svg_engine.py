class SVGEngine:

    def __init__(self, scale=50, wall=3):
        self.scale = scale
        self.wall = wall

    # ======================
    # MAIN RENDER
    # ======================
    def render(self, spatial_data):

        nodes = spatial_data["nodes"]

        width = spatial_data["width"] * self.scale
        height = spatial_data["height"] * self.scale

        svg = []

        # ======================
        # BACKGROUND
        # ======================
        svg.append(f"""
        <rect width="{width}" height="{height}" fill="white"/>
        """)

        # ======================
        # ROOM SHAPES (ARCHITECTURAL WALLS)
        # ======================
        for name, n in nodes.items():

            x = n["x"] * self.scale
            y = n["y"] * self.scale
            w = n["w"] * self.scale
            h = n["h"] * self.scale

            # outer wall
            svg.append(f"""
            <rect
                x="{x}" y="{y}"
                width="{w}" height="{h}"
                fill="none"
                stroke="black"
                stroke-width="{self.wall}"
            />
            """)

            # label
            svg.append(f"""
            <text x="{x+5}" y="{y+15}" font-size="12">
                {name}
            </text>
            """)

        # ======================
        # DOOR PLACEMENT (INTELLIGENT)
        # ======================
        drawn = set()

        for name, n in nodes.items():

            cx = (n["x"] + n["w"]/2) * self.scale
            cy = (n["y"] + n["h"]/2) * self.scale

            for conn in n["connections"]:

                if conn not in nodes:
                    continue

                pair = tuple(sorted([name, conn]))
                if pair in drawn:
                    continue
                drawn.add(pair)

                t = nodes[conn]

                tx = (t["x"] + t["w"]/2) * self.scale
                ty = (t["y"] + t["h"]/2) * self.scale

                # detect dominant axis (architectural logic)
                dx = abs(cx - tx)
                dy = abs(cy - ty)

                # door position on shared wall direction
                if dx > dy:
                    # horizontal connection
                    door_x = (cx + tx) / 2
                    door_y = cy
                else:
                    # vertical connection
                    door_x = cx
                    door_y = (cy + ty) / 2

                # door opening (gap)
                svg.append(f"""
                <rect
                    x="{door_x - 5}"
                    y="{door_y - 2}"
                    width="10"
                    height="4"
                    fill="brown"
                />
                """)

                # connection guide (faint)
                svg.append(f"""
                <line
                    x1="{cx}" y1="{cy}"
                    x2="{tx}" y2="{ty}"
                    stroke="gray"
                    stroke-width="1"
                    opacity="0.3"
                />
                """)

        # ======================
        # FINAL SVG
        # ======================
        return f"""
        <svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
            {''.join(svg)}
        </svg>
        """