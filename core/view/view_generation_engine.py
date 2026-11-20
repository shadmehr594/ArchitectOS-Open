class ViewGenerationEngine:

    def generate(self, spatial, structure=None):

        return {
            "plans": self._generate_plans(spatial),
            "sections": self._generate_sections(spatial),
            "elevations": self._generate_elevations(spatial),
            "cameras": self._generate_cameras(spatial)
        }

    # ======================
    # FLOOR PLANS
    # ======================
    def _generate_plans(self, spatial):

        plans = {}

        for floor, data in spatial.items():

            plans[floor] = {
                "type": "2D_PLAN",
                "elements": [
                    {
                        "node": node,
                        "x": props["x"],
                        "y": props["y"],
                        "w": props["w"],
                        "h": props["h"]
                    }
                    for node, props in data["nodes"].items()
                ]
            }

        return plans

    # ======================
    # SECTIONS
    # ======================
    def _generate_sections(self, spatial):

        sections = []

        for floor, data in spatial.items():

            sections.append({
                "name": f"{floor}_SECTION",
                "cut_line": "AUTO",
                "elements": list(data["nodes"].keys())
            })

        return sections

    # ======================
    # ELEVATIONS
    # ======================
    def _generate_elevations(self, spatial):

        elevations = []

        for floor in spatial.keys():

            elevations.append({
                "name": f"{floor}_ELEVATION",
                "type": "FRONT_VIEW"
            })

        return elevations

    # ======================
    # CAMERA SYSTEM (CRITICAL FOR COMFYUI)
    # ======================
    def _generate_cameras(self, spatial):

        cameras = []

        for i, floor in enumerate(spatial.keys()):

            cameras.append({
                "name": f"{floor}_CAM",
                "position": [i * 10, 10, 8],
                "look_at": [0, 0, 0],
                "fov": 60,
                "purpose": "RENDER"
            })

        return cameras