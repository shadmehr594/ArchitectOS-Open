# ==========================================================
# ArchitectOS v1.0
# Core Tool Bootstrap
# ==========================================================

from core.tool_registry import ToolRegistry

from core.tools.chat_tool import ChatTool
from core.tools.memory_tool import MemoryTool
from core.tools.image_tool import ImageTool
from core.tools.design_tool import DesignTool


def build_tool_registry(
        brain=None,
        memory=None
):

    registry = ToolRegistry()


    # ==========================
    # CHAT
    # ==========================

    registry.register(
        "chat",
        ChatTool(
            brain=brain,
            memory=memory
        )
    )


    # ==========================
    # MEMORY
    # ==========================

    if memory:

        registry.register(
            "memory",
            MemoryTool(
                memory
            )
        )


    # ==========================
    # IMAGE
    # ==========================

    registry.register(
        "image",
        ImageTool()
    )


    # ==========================
    # DESIGN
    # ==========================

    registry.register(
        "design",
        DesignTool()
    )


    print(
        "🚀 TOOL REGISTRY READY:",
        registry.list_tools()
    )


    return registry