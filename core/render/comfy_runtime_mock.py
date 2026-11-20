import time

class ComfyClient:

    def __init__(self, endpoint="http://127.0.0.1:8188"):
        self.endpoint = endpoint

    # ======================
    # MOCK RENDER RESULT
    # ======================
    def get_result(self, prompt_payload):

        print("🎨 WAITING FOR COMFY RENDER...")

        # شبیه‌سازی delay رندر
        time.sleep(2)

        # در نسخه واقعی اینجا image URL میاد
        return {
            "status": "done",
            "image_url": "http://127.0.0.1:8188/output/fake_render.png",
            "message": "Render completed"
        }