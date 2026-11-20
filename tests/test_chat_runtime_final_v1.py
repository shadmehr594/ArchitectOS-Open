# ==========================================================
# ArchitectOS Chat Runtime Final Hardening Test v1
# Full Session Stability Test
# ==========================================================


from core.chat.chat_architect import ChatArchitect
from core.brain import Brain


print("\n🚀 CHAT RUNTIME FINAL HARDENING TEST v1 START\n")


brain = Brain()

chat = ChatArchitect(
    brain
)


messages = [

    "سلام",

    "یک ویلای مدرن طراحی کن",

    "یک اتاق کودک به آن اضافه کن",

    "یک استخر اضافه کن",

    "نمای مدرن برای آن بساز",

    "یک تصویر بساز",

    "ویلایی که قبلا طراحی کردیم را توضیح بده"

]


for msg in messages:

    print("\n====================")
    print("USER:")
    print(msg)


    result = chat.process(
        msg
    )


    print("\nRESULT TYPE:")

    print(
        result.get("type")
    )


    print("\nSTATUS:")

    print(
        result.get("status")
    )


print("\n====================")

print("FINAL STATE")

state = chat.state.get()

print(state)


print("\n====================")


print(
    "LAST DESIGN KEYS:",
    list(
        state.get(
            "last_design",
            {}
        ).keys()
    )
)


print("\n✅ CHAT RUNTIME FINAL HARDENING TEST v1 COMPLETE")