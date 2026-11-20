# ==========================================================
# ArchitectOS Chat LLM Routing Debug v1
#
# Test:
# ChatArchitect
#     |
#     + Chat -> Gemma
#     |
#     + Semantic -> Qwen
#
# No Render
# No ComfyUI
# ==========================================================


from core.llm.model_router import model_router
from core.llm.llm_gateway_v30 import llm_gateway



print("\n================================")
print("🧠 CHAT LLM ROUTING TEST START")
print("================================\n")



# ==========================================================
# CHAT
# ==========================================================

print("\n===== NORMAL CHAT =====")


chat = model_router.generate(

    """
سلام.
اسم من را نمی‌دانی، فقط خودت را معرفی کن.
""",

    task="chat"

)


print("\nCHAT MODEL OUTPUT:\n")

print(chat)



# ==========================================================
# ARCHITECTURE
# ==========================================================

print("\n===== ARCHITECTURE REASONING =====")


architecture = model_router.generate(

    """
درخواست معماری:

یک ویلای مدرن با نمای شیشه و بتن طراحی کن.
خروجی باید JSON معماری باشد.
""",

    task="architecture"

)


print("\nARCHITECTURE MODEL OUTPUT:\n")

print(architecture)



# ==========================================================
# MODEL CHECK
# ==========================================================

print("\n===== MODEL MAP =====")

print(
    "CHAT MODEL:",
    llm_gateway.MODELS["chat"]
)


print(
    "REASONING MODEL:",
    llm_gateway.MODELS["reasoning"]
)


print(
    "BACKUP MODEL:",
    llm_gateway.MODELS["backup"]
)



print("\n================================")
print("✅ CHAT LLM ROUTING TEST COMPLETE")
print("================================")