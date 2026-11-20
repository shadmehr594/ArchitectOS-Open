class ComfyBridge:

    def generate_prompt(self, bim_result):

        spatial = bim_result.get("spatial", {})

        prompt = "architectural visualization, ultra realistic building"

        for floor, data in spatial.items():

            prompt += f", {floor} modern layout"

        return {
            "prompt": prompt,
            "negative": "low quality, cartoon, distorted"
        }

    def send_to_comfy(self, prompt_data):

        # placeholder for API call
        return {
            "status": "sent_to_comfy",
            "prompt": prompt_data
        }