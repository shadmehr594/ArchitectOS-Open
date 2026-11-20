# ==========================================================
# ArchitectOS Project Persistence Test v1
# Save / Reload / Continue Design State
# ==========================================================


from core.chat.chat_architect import ChatArchitect
from core.brain import Brain


print("\n🚀 PROJECT PERSISTENCE TEST v1 START\n")


# ==========================================
# SESSION 1
# ==========================================

print("\n--- SESSION 1 ---\n")


brain1 = Brain()

chat1 = ChatArchitect(
    brain1
)


messages = [

    "یک ویلای مدرن طراحی کن",

    "یک اتاق کودک به آن اضافه کن",

    "یک استخر اضافه کن"

]


for msg in messages:

    print("\nUSER:")
    print(msg)

    result = chat1.process(
        msg
    )

    print(
        "TYPE:",
        result.get("type")
    )

    print(
        "STATUS:",
        result.get("status")
    )



saved_state = chat1.state.get()


print("\nSAVED STATE KEYS:")

print(
    saved_state.keys()
)


print(
    "\nSAVED DESIGN:"
)

print(
    saved_state.get(
        "last_design"
    )
)



# ==========================================
# SESSION 2 (NEW INSTANCE)
# ==========================================

print("\n\n--- SESSION 2 RESTART ---\n")


brain2 = Brain()

chat2 = ChatArchitect(
    brain2
)


result = chat2.process(
    "ویلایی که قبلا طراحی کردیم را ادامه بده"
)


print("\nRESULT:")

print(result)


print("\nFINAL STATE:")

print(
    chat2.state.get()
)



print(
    "\n✅ PROJECT PERSISTENCE TEST v1 COMPLETE"
)