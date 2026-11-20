import random

class WorkflowCompiler:

    def __init__(self):
        pass

    def build_flux_workflow(self, prompt: str):

        print("[v12 COMPILER] building validated FLUX graph...")

        seed = random.randint(1, 999999999)

        workflow = {
            "202": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": "flux1-krea-dev_fp8_scaled.safetensors",
                    "weight_dtype": "default"
                }
            },

            "204": {
                "class_type": "DualCLIPLoader",
                "inputs": {
                    "clip_name1": "clip_l.safetensors",
                    "clip_name2": "t5xxl_fp16.safetensors",
                    "type": "flux"
                }
            },

            "205": {
                "class_type": "VAELoader",
                "inputs": {
                    "vae_name": "ae.safetensors"
                }
            },

            "206": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["204", 0]
                }
            },

            "212": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "low quality, blurry",
                    "clip": ["204", 0]
                }
            },

            "211": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": 736,
                    "height": 704,
                    "batch_size": 1
                }
            },

            "210": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": 20,
                    "cfg": 3.5,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "denoise": 1,
                    "model": ["202", 0],
                    "positive": ["206", 0],
                    "negative": ["212", 0],
                    "latent_image": ["211", 0]
                }
            },

            "208": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["210", 0],
                    "vae": ["205", 0]
                }
            },

            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "ArchitectOS_v12",
                    "images": ["208", 0]
                }
            }
        }

        return workflow