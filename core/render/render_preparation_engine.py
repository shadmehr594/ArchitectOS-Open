class RenderPreparationEngine:

    def prepare(self, views, spatial):

        return {
            "images": self._image_targets(views),
            "depth_maps": self._depth_maps(spatial),
            "prompts": self._generate_prompts(spatial),
            "animation_paths": self._animation_paths(views)
        }

    # ======================
    # IMAGE TARGETS
    # ======================
    def _image_targets(self, views):

        return [
            {
                "type": "RENDER_TARGET",
                "source": cam["name"],
                "resolution": "1024x1024"
            }
            for cam in views.get("cameras", [])
        ]

    # ======================
    # DEPTH MAPS (FOR COMFYUI CONTROLNET)
    # ======================
    def _depth_maps(self, spatial):

        return {
            floor: {
                node: {
                    "depth": props["y"] * 0.1
                }
                for node, props in data["nodes"].items()
            }
            for floor, data in spatial.items()
        }

    # ======================
    # AI PROMPTS (FOR RENDER STYLE)
    # ======================
    def _generate_prompts(self, spatial):

        return [
            f"modern architectural visualization of {floor}, realistic lighting, high detail"
            for floor in spatial.keys()
        ]

    # ======================
    # ANIMATION PATHS (WALKTHROUGH)
    # ======================
    def _animation_paths(self, views):

        return {
            "walkthrough": [
                cam["position"]
                for cam in views.get("cameras", [])
            ]
        }