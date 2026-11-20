# ==========================================================
# ArchitectOS Design Continuation Test v1
# Multi-step Design Update + Conversation State
# ==========================================================


from core.chat.chat_architect import ChatArchitect
from core.brain import Brain


print("\n🚀 DESIGN CONTINUATION TEST v1 START\n")


brain = Brain()


chat = ChatArchitect(
    brain
)


messages = [

    "سلام",

    "یک ویلای مدرن طراحی کن",

    "یک اتاق کودک به آن اضافه کن",

    "یک استخر به آن اضافه کن",

    "نمای مدرن برای آن بساز"

]


for msg in messages:

    print("\n====================")

    print("USER:")
    print(msg)


    result = chat.process(
        msg
    )


    print("\nRESULT:")

    print(result)



print("\n====================")

print("FINAL CONVERSATION STATE:")

print(
    chat.state.get()
)


print("\n✅ DESIGN CONTINUATION TEST v1 COMPLETE")