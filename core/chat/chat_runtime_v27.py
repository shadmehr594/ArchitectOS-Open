# ==========================================================
# ArchitectOS Chat Runtime v27
# Unified Runtime Wrapper
# Handle Adapter Edition
# ==========================================================

from core.chat.chat_runtime_v26 import ChatRuntimeV26


class ChatRuntimeV27:

    VERSION = "27.1"

    def __init__(
        self,
        architect
    ):

        self.architect = architect

        self.runtime = ChatRuntimeV26(
            architect
        )

        print(
            "💬 CHAT RUNTIME v27 ONLINE"
        )

    # ======================================================
    # HANDLE
    # ======================================================

    def handle(
        self,
        user,
        context=None
    ):

        if context is None:
            context = {}

        return self.runtime.handle(
            user,
            context=context
        )

    # ======================================================
    # RUN ALIAS
    # ======================================================

    def run(
        self,
        user,
        context=None
    ):

        return self.handle(
            user,
            context=context
        )


# ==========================================================
# FACTORY
# ==========================================================

chat_runtime = None


def create_chat_runtime_v27(
    architect
):

    global chat_runtime

    chat_runtime = ChatRuntimeV27(
        architect
    )

    return chat_runtime