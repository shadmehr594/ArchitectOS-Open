# ==========================================================
# ArchitectOS Chat Runtime v26
# Unified Runtime Pipeline
# Brain Bridge Edition
# ==========================================================

import traceback

from core.chat.response_contract import response_contract


class ChatRuntimeV26:

    VERSION = "v26.1"

    def __init__(
        self,
        architect
    ):

        self.architect = architect
        self.brain = architect.get_brain()

        print(
            "💬 CHAT RUNTIME v26 ONLINE"
        )

    # ======================================================
    # HANDLE
    # ======================================================

    def handle(
        self,
        message,
        context=None
    ):

        if context is None:
            context = {}

        try:

            # ==========================================
            # ROUTE TO GOD CORE BRAIN
            # ==========================================

            result = self.brain.run(
                message,
                context=context
            )

            if isinstance(result, dict):

                return response_contract.build(

                    result.get(
                        "type",
                        "chat"
                    ),

                    result.get(
                        "engine",
                        "brain"
                    ),

                    result.get(
                        "result"
                    ),

                    result.get(
                        "status",
                        "success"
                    )

                )

            return response_contract.success(

                "brain",

                result

            )

        except Exception as e:

            traceback.print_exc()

            return response_contract.error(

                "chat_runtime_v26",

                str(e)

            )