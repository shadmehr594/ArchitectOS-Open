from core.chat.chat_runtime_v29 import chat_runtime


print("\n===== CHAT =====")
print(
    chat_runtime.run(
        "سلام"
    )
)


print("\n===== DESIGN =====")
print(
    chat_runtime.run(
        "یک ویلای مدرن طراحی کن",
        metadata={
            "source":"test"
        }
    )
)


print("\n===== IMAGE =====")
print(
    chat_runtime.run(
        "draw a modern house"
    )
)