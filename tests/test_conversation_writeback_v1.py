# ==========================================================
# ArchitectOS Conversation Write-Back Test
# ==========================================================


from core.memory.memory_manager import memory_manager

from core.memory.conversation_writeback import (
    ConversationWriteBack
)



print(
    "\n🧠 CONVERSATION WRITE-BACK TEST START\n"
)



writer = ConversationWriteBack(
    memory_manager
)



result = writer.store(

    "برای بچه ها یک اتاق طراحی کن",

    "یک اتاق مدرن و امن برای کودکان پیشنهاد می‌کنم"

)



print(
    "\nSTORE RESULT:"
)

print(result)



print(
    "\nHISTORY:"
)


try:

    print(
        memory_manager.get_history(5)
    )

except Exception as e:

    print(
        "HISTORY ERROR:",
        e
    )



print(
    "\n✅ CONVERSATION WRITE-BACK TEST COMPLETE"
)