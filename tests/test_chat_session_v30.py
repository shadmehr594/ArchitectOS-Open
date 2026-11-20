# ==========================================================
# ArchitectOS Chat Session Runtime v30 Test
# Full Context + Memory + Conversation State
# ==========================================================


from core.chat.chat_architect import ChatArchitect
from core.brain import Brain


print("\n🚀 CHAT SESSION v30 TEST START\n")


brain = Brain()


chat = ChatArchitect(
    brain
)


messages = [

    "سلام",

    "یک ویلای مدرن طراحی کن",

    "یک اتاق کودک به آن اضافه کن",

    "یک تصویر بساز"

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


print("\n✅ CHAT SESSION v30 TEST COMPLETE")