# ==========================================================
# ArchitectOS Design Memory Continuation Test v2
# Verify previous_design propagation
# ==========================================================


from core.chat.chat_architect import ChatArchitect
from core.brain import Brain


print("\n🚀 DESIGN MEMORY CONTINUATION TEST v2 START\n")


brain = Brain()

chat = ChatArchitect(
    brain
)


steps = [

    "یک ویلای مدرن طراحی کن",

    "یک اتاق کودک به آن اضافه کن",

    "یک استخر به آن اضافه کن"

]


for step in steps:

    print("\n====================")
    print("USER:")
    print(step)


    result = chat.process(
        step
    )


    print("\nRESULT TYPE:")
    print(
        result.get("type")
    )


    if result.get("result"):

        data = result["result"]

        if isinstance(data, dict):

            print(
                "OPERATION:",
                data.get("operation")
            )

            print(
                "HAS PREVIOUS DESIGN:",
                data.get("has_previous_design")
            )



print("\n====================")
print("FINAL DESIGN CHECK")


state = chat.state.get()


design = state.get(
    "last_design"
)


print(
    "LAST DESIGN KEYS:",
    list(design.keys())
    if isinstance(design, dict)
    else type(design)
)


print("\n✅ DESIGN MEMORY CONTINUATION TEST v2 COMPLETE")