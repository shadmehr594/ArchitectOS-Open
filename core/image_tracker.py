import os

class ImageTracker:

    def __init__(self, path="D:/ComfyUI/output"):
        self.path = path

    def latest(self):
        if not os.path.exists(self.path):
            return None

        files = [f for f in os.listdir(self.path) if f.endswith(".png")]

        if not files:
            return None

        files.sort(key=lambda x: os.path.getmtime(os.path.join(self.path, x)))

        return os.path.join(self.path, files[-1])