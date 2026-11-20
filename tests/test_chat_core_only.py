# ==========================================================
# ArchitectOS Chat Core Only Test v1.0
# No Design / No Image / No Render
# ==========================================================

from core.app_boot import AppBoot
from core.chat.chat_architect import ChatArchitect


print("\n🚀 CHAT CORE ONLY TEST START\n")


# BOOT
app = AppBoot()

brain = app.get_brain()


print("\n🧠 BRAIN READY")
print(type(brain))


# CHAT GATEWAY
chat = ChatArchitect(
    brain
)


print("\n💬 CHAT GATEWAY READY")


# ==================================================
# TEST 1 - SIMPLE CHAT
# ==================================================

print("\n===== SIMPLE CHAT =====")

result = chat.handle(
    "سلام"
)

print(result)


# ==================================================
# TEST 2 - ARCHITECTURAL KNOWLEDGE QUESTION
# ==================================================

print("\n===== KNOWLEDGE CHAT =====")

result = chat.handle(
    "تفاوت معماری مدرن و مینیمال چیست؟"
)

print(result)


# ==================================================
# TEST 3 - MEMORY RECALL
# ==================================================

print("\n===== MEMORY CHAT =====")

result = chat.handle(
    "اسم من چیست؟"
)

print(result)


print("\n✅ CHAT CORE ONLY TEST COMPLETE\n")