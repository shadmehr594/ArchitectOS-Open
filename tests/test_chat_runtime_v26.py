# ==========================================================
# ArchitectOS Chat Runtime v26 Test
# ==========================================================


from core.app_boot import AppBoot
from core.chat.chat_architect import ChatArchitect
from core.chat.chat_runtime_v26 import ChatRuntimeV26



print("\n🚀 CHAT RUNTIME v26 TEST START\n")



app = AppBoot()


brain = app.brain



chat_architect = ChatArchitect(
    brain
)



runtime = ChatRuntimeV26(
    chat_architect
)



print("\n===== CHAT =====\n")


result = runtime.handle(
    "سلام"
)


print(result)



print("\n===== DESIGN =====\n")


result = runtime.handle(
    "یک ویلای مدرن طراحی کن"
)


print(result)



print("\n===== IMAGE =====\n")


result = runtime.handle(
    "draw a modern house"
)


print(result)



print("\n✅ CHAT RUNTIME v26 TEST COMPLETE\n")