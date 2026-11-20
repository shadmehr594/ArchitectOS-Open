# ==========================================================
# ArchitectOS Conversation WriteBack Bridge v1
# Compatibility Layer
# ==========================================================


from .conversation_memory import (
    ConversationWriteBack,
    create_writeback
)


__all__ = [
    "ConversationWriteBack",
    "create_writeback"
]