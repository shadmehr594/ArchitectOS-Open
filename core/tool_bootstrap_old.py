# ==========================================================
# ArchitectOS Tool Bootstrap v22
# Unified Tool Registration Layer
# BIM + COMFY + VOICE
# ==========================================================


from core.tool_registry import ToolRegistry


# ======================
# CORE TOOLS
# ======================

from tools.bim_tool import BIMTool
from tools.comfy_tool import ComfyTool

from tools.speech_to_text import SpeechToTextTool
from tools.text_to_speech import TextToSpeechTool


# ======================
# COMFY CLIENT
# ======================

try:

    from skills.comfyui.client import send_workflow

    class ComfyClient:

        def generate(self, workflow):

            return send_workflow(
                workflow
            )


    COMFY_AVAILABLE = True


except Exception as e:

    print(
        "⚠️ COMFY CLIENT NOT AVAILABLE:",
        e
    )

    COMFY_AVAILABLE = False





def build_tool_registry(

    spatial_engine=None,
    graph_engine=None,
    validator=None,
    comfy_client=None

):


    registry = ToolRegistry()



    # ==================================================
    # BIM TOOL
    # ==================================================

    if (

        spatial_engine
        and graph_engine
        and validator

    ):


        registry.register(

            "bim",

            BIMTool(

                spatial_engine,
                graph_engine,
                validator

            )

        )



    # ==================================================
    # COMFY IMAGE TOOL
    # ==================================================

    if comfy_client is None and COMFY_AVAILABLE:


        comfy_client = ComfyClient()



    if comfy_client:


        registry.register(

            "image",

            ComfyTool(

                comfy_client

            )

        )



    # ==================================================
    # VOICE SYSTEM
    # ==================================================

    registry.register(

        "speech_to_text",

        SpeechToTextTool()

    )


    registry.register(

        "text_to_speech",

        TextToSpeechTool()

    )



    print(

        "🛠️ TOOL REGISTRY READY:",

        registry.list_tools()

    )


    return registry