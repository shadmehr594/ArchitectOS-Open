class AnimationEngine:

    def build_walkthrough(self, views, spatial):

        path = self._build_path(views)
        keyframes = self._build_keyframes(path)
        shots = self._build_shots(spatial, keyframes)

        return {
            "path": path,
            "keyframes": keyframes,
            "shots": shots,
            "video_settings": self._video_settings()
        }

    # ======================
    # CAMERA PATH GENERATION
    # ======================
    def _build_path(self, views):

        path = []

        for cam in views.get("cameras", []):

            path.append({
                "position": cam["position"],
                "look_at": cam["look_at"],
                "fov": cam["fov"],
                "speed": 1.0
            })

        return path

    # ======================
    # KEYFRAMES (IMPORTANT FOR VIDEO)
    # ======================
    def _build_keyframes(self, path):

        keyframes = []

        for i, p in enumerate(path):

            keyframes.append({
                "frame": i * 30,
                "camera_position": p["position"],
                "look_at": p["look_at"],
                "interpolation": "linear"
            })

        return keyframes

    # ======================
    # SHOT GENERATION (ARCHITECTURAL LOGIC)
    # ======================
    def _build_shots(self, spatial, keyframes):

        shots = []

        for floor, data in spatial.items():

            shots.append({
                "name": f"{floor}_SHOT",
                "focus": list(data["nodes"].keys())[:5],
                "keyframe_range": (0, len(keyframes))
            })

        return shots

    # ======================
    # VIDEO SETTINGS
    # ======================
    def _video_settings(self):

        return {
            "fps": 24,
            "resolution": "1920x1080",
            "format": "mp4",
            "duration_estimate_sec": 10
        }

    # ======================
    # EXPORT FOR COMFYUI / BLENDER
    # ======================
    def export_for_render(self, animation):

        return {
            "type": "ANIMATION_EXPORT",
            "frames": animation["keyframes"],
            "camera_path": animation["path"],
            "render_mode": "WALKTHROUGH"
        }