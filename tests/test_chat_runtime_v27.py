# ==========================================================
# ArchitectOS Chat Runtime v27 Test
# ==========================================================


from core.app_boot import AppBoot
from core.chat.chat_runtime_v27 import create_chat_runtime_v27



print("\n🚀 CHAT RUNTIME v27 TEST START\n")


app = AppBoot()


runtime = create_chat_runtime_v27(
    app
)


print("\n===== CHAT =====\n")

print(
    runtime.run(
        "سلام"
    )
)


print("\n===== DESIGN =====\n")

print(
    runtime.run(
        "یک ویلای مدرن طراحی کن"
    )
)


print("\n===== IMAGE =====\n")

print(
    runtime.run(
        "draw a modern house"
    )
)


print(
    "\n✅ CHAT RUNTIME v27 TEST COMPLETE\n"
)