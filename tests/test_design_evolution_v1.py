# ==========================================================
# ArchitectOS Design Evolution Test v1
# Design Memory + Continuation + Evolution
# ==========================================================


from core.chat.chat_architect import ChatArchitect
from core.brain import Brain


print("\n🚀 DESIGN EVOLUTION TEST v1 START\n")


brain = Brain()


chat = ChatArchitect(
    brain
)


messages = [

    "سلام",

    "یک ویلای مدرن طراحی کن",

    "یک اتاق کودک به آن اضافه کن",

    "یک استخر به آن اضافه کن",

    "یک نمای مدرن برای آن بساز",

    "یک تصویر بساز"

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
        result.get(
            "type"
        )
    )


    print("\nRESULT:")

    print(
        result
    )



print("\n====================")

print("FINAL STATE")


state = chat.state.get()


print(
    state
)


print("\n====================")

print("FINAL DESIGN KEYS:")


if state.get(
    "last_design"
):

    print(
        list(
            state[
                "last_design"
            ].keys()
        )
    )


print("\n✅ DESIGN EVOLUTION TEST v1 COMPLETE")