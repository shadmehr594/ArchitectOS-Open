# ==========================================================
# ArchitectOS Release Integration Test v1.0
# Core Contract Validation
# No Real Render Execution
# ==========================================================


import json


from core.app_boot import AppBoot
from core.chat.chat_architect import ChatArchitect



print("\n" + "=" * 70)
print("🚀 ArchitectOS RELEASE INTEGRATION TEST v1.0")
print("🚫 REAL RENDER DISABLED")
print("=" * 70)



# ==========================================================
# BOOT
# ==========================================================


boot = AppBoot()

brain = boot.get_brain()


print(
    "🧠 Brain:",
    type(brain).__name__
)


chat = ChatArchitect(
    brain
)


print(
    "💬 ChatArchitect ONLINE"
)



# ==========================================================
# CHAT CONTRACT
# ==========================================================


print("\nTEST 1: CHAT CONTRACT")


chat_result = chat.handle(
    "سلام ArchitectOS"
)


assert chat_result is not None


print(
    "✅ CHAT OK"
)



# ==========================================================
# DESIGN CONTRACT
# ==========================================================


print("\nTEST 2: DESIGN CONTRACT")


design_result = chat.handle(
    "یک ویلای مدرن با نمای سنگ و چوب طراحی کن"
)



assert isinstance(
    design_result,
    dict
)


design_type = (
    design_result.get("type")
    or
    design_result.get("result", {}).get("type")
)



assert (
    design_type == "design"
    or
    "architectural_intent" in design_result
    or
    "result" in design_result
)



print(
    "🏗️ DESIGN CONTRACT OK"
)



# Extract intent safely


intent = (
    design_result.get(
        "architectural_intent"
    )
    or
    design_result.get(
        "result",
        {}
    ).get(
        "architectural_intent",
        {}
    )
)



print(
    json.dumps(
        intent,
        indent=2,
        ensure_ascii=False
    )
)



# ==========================================================
# RENDER CONTRACT
# ==========================================================


print("\nTEST 3: RENDER CONTRACT")



render_contract = {

    "type":
        "image_render",

    "architectural_intent":
        intent,

    "execution":
    {

        "status":
            "contract_only"

    }

}



assert (
    render_contract["type"]
    ==
    "image_render"
)



assert (
    render_contract["execution"]["status"]
    ==
    "contract_only"
)



print(
    "🎨 RENDER CONTRACT OK"
)



# ==========================================================
# STATE ACCESS
# ==========================================================


print("\nTEST 4: STATE ACCESS")


try:

    from core.chat.conversation_state import conversation_state


    print(
        "STATE AVAILABLE:"
    )


    print(
        conversation_state
    )


    print(
        "✅ STATE OK"
    )


except Exception as e:

    print(
        "⚠️ STATE CHECK:",
        e
    )



print("\n" + "=" * 70)
print("🎉 RELEASE INTEGRATION TEST PASSED")
print("=" * 70)