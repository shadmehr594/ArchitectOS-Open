from core.tool_interface import BaseTool

from skills.comfyui.comfy_runtime import ComfyRuntime



class ComfyTool(BaseTool):


    name = "image"



    def __init__(
        self,
        client=None
    ):

        self.runtime = ComfyRuntime()



    def execute(
        self,
        input_text
    ):

        print(
            "🎨 COMFY TOOL v3 ACTIVE"
        )


        return self.runtime.generate(
            input_text
        )